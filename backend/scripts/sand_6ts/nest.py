"""6 TS anidado en el 2 TS día/noche: cada bloque nuevo cae dentro de un solo bloque del 2 TS.

Bloques por semestre: madrugada 00–06 (S_01), día 06–18 (S_02), noche 18–24 (S_03).
El día del 6 TS cae en el día del 2 TS (S101); madrugada y noche, en la noche (S102).
La hora 17–18 se pasa de la tarde-noche de la UPME (17–24) al día como 1/7 de ese
bloque. Por bloque del 2 TS se conservan las horas, la demanda de cada fuel y la
energía de cada tecnología; de la UPME solo se toma la forma dentro del bloque.

Supuesto a confirmar con la UPME: el día del 2 TS va de 06 a 18 h (el SAND solo dice 12 h/12 h).
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

from common import (
    SHAPES_SAND, _rows, check_peak_capacity, clean_shapes, read_sand, replace_params, scale_peak_capacity,
    validate, write_sand, year_columns,
)

NEW_TS = ["S101", "S102", "S103", "S201", "S202", "S203"]
# Bloque del 6 TS → bloque del 2 TS que lo contiene (S101 = día, S102 = noche).
PARENT = {"S101": "S102", "S102": "S101", "S103": "S102",
          "S201": "S102", "S202": "S101", "S203": "S102"}
TOL = 1e-9


def children(parent: dict[str, str]) -> dict[str, list[str]]:
    return {p: [c for c in parent if parent[c] == p] for p in ("S101", "S102")}


def reblock(e: pd.DataFrame) -> pd.DataFrame:
    """Cantidad aditiva por TS de la UPME (horas o energía) → bloques nuevos."""
    out = {}
    for s in ("S1", "S2"):
        out[f"{s}01"] = e.loc[f"{s}01"]
        out[f"{s}02"] = e.loc[f"{s}02"] + e.loc[f"{s}03"] / 7
        out[f"{s}03"] = e.loc[f"{s}03"] * 6 / 7
    return pd.DataFrame(out).T.loc[NEW_TS]


def distribute(target: float, weights: np.ndarray, hours: np.ndarray) -> np.ndarray:
    """Reparte la energía ``target`` según ``weights`` con CF ≤ 1; el excedente va a los hermanos."""
    cf = np.zeros_like(hours)
    free = np.ones(len(hours), dtype=bool)
    left = target
    for _ in range(len(hours) + 1):
        if not free.any() or left <= TOL:
            return np.where(free, 0.0, cf)
        w = weights * free
        if w.sum() <= 0:
            w = hours * free
        share = left * w / w.sum()
        cand = np.where(free, share / hours, cf)
        over = free & (cand > 1 + TOL)
        if not over.any():
            return np.where(free, cand, cf)
        cf[over] = 1.0
        left -= hours[over].sum()
        free &= ~over
    raise ValueError("No cabe la energía del padre con CF ≤ 1.")


def build_nested(base: pd.DataFrame, shapes: pd.DataFrame, years: list[str], flat: bool = False,
                 free_shape: tuple[str, ...] = ()) -> dict:
    """YearSplit, SpecifiedDemandProfile y CapacityFactor del 6 TS anidado (``flat``: formas planas).

    ``free_shape``: prefijos de tecnologías cuya energía anual del 2 TS se reparte entre los
    seis bloques con la forma de la UPME, sin respetar el día y la noche del 2 TS (p. ej. la
    eólica, que en el 2 TS es plana día/noche). El resto sigue anidado.
    """
    kids = children(PARENT)
    ys2 = base[base["Parameter"] == "YearSplit"].set_index("TIMESLICE")[years].astype(float)
    ys_upme = shapes[shapes["Parameter"] == "YearSplit"].set_index("TIMESLICE")[years].astype(float)
    # La UPME redondea a 6 decimales; con horas enteras el día suma exactamente 4380 h.
    ys_upme = (ys_upme * 8760).round() / 8760
    ys = reblock(ys_upme)

    ys_rows = shapes[shapes["Parameter"] == "YearSplit"].reset_index(drop=True).copy()
    ys_rows["TIMESLICE"] = NEW_TS if list(ys_rows["TIMESLICE"]) == NEW_TS else None
    ys_rows[years] = ys.to_numpy()
    if base.loc[base["Parameter"] == "YearSplit", "REGION"].isna().all():
        ys_rows["REGION"] = None

    # Demanda: forma común de la UPME reagrupada, reescalada a cada bloque del 2 TS.
    sdp6 = shapes[shapes["Parameter"] == "SpecifiedDemandProfile"].groupby("TIMESLICE")[years].mean()
    shape = ys if flat else reblock(sdp6)
    sdp2 = base[base["Parameter"] == "SpecifiedDemandProfile"]
    sdp_rows = []
    for (region, fuel), g in sdp2.groupby(["REGION", "FUEL"], sort=False):
        parent = g.set_index("TIMESLICE")[years].astype(float)
        for c in NEW_TS:
            sib = kids[PARENT[c]]
            val = parent.loc[PARENT[c]] * shape.loc[c] / shape.loc[sib].sum()
            sdp_rows.append(_rows(base, "SpecifiedDemandProfile",
                                  {"REGION": region, "FUEL": fuel, "TIMESLICE": c}, val))

    # CF: energía del bloque del 2 TS repartida con la forma de la UPME (por energía).
    cf2 = base[base["Parameter"] == "CapacityFactor"]
    cf6 = shapes[shapes["Parameter"] == "CapacityFactor"]
    cf_rows = []
    for (region, tech), g in cf2.groupby(["REGION", "TECHNOLOGY"], sort=False):
        parent = g.set_index("TIMESLICE")[years].astype(float)
        s6 = cf6[(cf6["REGION"] == region) & (cf6["TECHNOLOGY"] == tech)]
        energy = None if (flat or s6.empty) else reblock(
            s6.set_index("TIMESLICE")[years].astype(float) * ys_upme)
        new = pd.DataFrame(index=NEW_TS, columns=years, dtype=float)
        if energy is not None and tech.startswith(free_shape or ("\0",)):
            for y in years:
                target = sum(parent.loc[p, y] * ys2.loc[p, y] for p in kids)
                new[y] = distribute(target, energy[y].to_numpy(), ys[y].to_numpy())
            for c in NEW_TS:
                cf_rows.append(_rows(base, "CapacityFactor",
                                     {"REGION": region, "TECHNOLOGY": tech, "TIMESLICE": c}, new.loc[c]))
            continue
        for p, sib in kids.items():
            for y in years:
                hours = ys.loc[sib, y].to_numpy()
                target = parent.loc[p, y] * ys2.loc[p, y]
                w = hours if energy is None else energy.loc[sib, y].to_numpy()
                new.loc[sib, y] = distribute(target, w, hours)
        for c in NEW_TS:
            cf_rows.append(_rows(base, "CapacityFactor",
                                 {"REGION": region, "TECHNOLOGY": tech, "TIMESLICE": c}, new.loc[c]))

    return {
        "YearSplit": ys_rows,
        "SpecifiedDemandProfile": pd.DataFrame(sdp_rows, columns=base.columns),
        "CapacityFactor": pd.DataFrame(cf_rows, columns=base.columns),
    }


def check_nesting(base: pd.DataFrame, blocks: dict, years: list[str], parent: dict[str, str] = PARENT,
                  free_shape: tuple[str, ...] = ()) -> list[str]:
    """Por bloque del 2 TS: horas, demanda y energía de cada tecnología iguales.

    Las tecnologías de ``free_shape`` solo deben conservar la energía anual del 2 TS.
    """
    errors = []
    kids = children(parent)
    ys2 = base[base["Parameter"] == "YearSplit"].set_index("TIMESLICE")[years].astype(float)
    ys = blocks["YearSplit"].set_index("TIMESLICE")[years].astype(float)
    if set(ys.index) != set(parent):
        errors.append(f"YearSplit: timeslices {sorted(ys.index)} ≠ mapa de anidamiento {sorted(parent)}.")
        return errors
    for p, sib in kids.items():
        if (ys.loc[sib].sum() - ys2.loc[p]).abs().max() > TOL:
            errors.append(f"YearSplit: hijos de {p} no suman el 2 TS.")
    for param, key, weight in (("SpecifiedDemandProfile", "FUEL", False), ("CapacityFactor", "TECHNOLOGY", True)):
        b2 = base[base["Parameter"] == param].set_index([key, "TIMESLICE"])[years].astype(float)
        bn = blocks[param].set_index([key, "TIMESLICE"])[years].astype(float)
        for k in b2.index.get_level_values(0).unique():
            if param == "CapacityFactor" and k.startswith(free_shape or ("\0",)):
                ref = sum(b2.loc[(k, p)] * ys2.loc[p] for p in kids)
                got = sum(bn.loc[(k, c)] * ys.loc[c] for c in parent)
                if (got - ref).abs().max() > 1e-8:
                    errors.append(f"{param}: {k} no reproduce la energía anual del 2 TS ({(got - ref).abs().max():.2e}).")
                continue
            for p, sib in kids.items():
                ref = b2.loc[(k, p)] * (ys2.loc[p] if weight else 1)
                got = sum(bn.loc[(k, c)] * (ys.loc[c] if weight else 1) for c in sib)
                if (got - ref).abs().max() > 1e-8:
                    errors.append(f"{param}: {k} en {p} no reproduce el 2 TS ({(got - ref).abs().max():.2e}).")
    return errors


def tech_peak_factors(base: pd.DataFrame, blocks: dict, years: list[str]) -> pd.DataFrame:
    """f por tecnología y año, con el mismo cálculo de ``scale_peak_capacity``."""
    ys = blocks["YearSplit"].set_index("TIMESLICE")[years]
    sdp = blocks["SpecifiedDemandProfile"]
    ratio = sdp[years].to_numpy() / ys.loc[sdp["TIMESLICE"]].to_numpy()
    peak = (pd.DataFrame(ratio, columns=years, index=sdp["FUEL"].to_numpy())
            .groupby(level=0).max().clip(lower=1.0))
    sad = base[base["Parameter"] == "SpecifiedAnnualDemand"].groupby("FUEL")[years].sum()
    peak = peak.loc[[f for f in peak.index if f not in sad.index or (sad.loc[f] > 0).any()]]
    oar = base[(base["Parameter"] == "OutputActivityRatio") & base["FUEL"].isin(peak.index)]
    oar = oar[(oar[years] > 0).any(axis=1)]
    return peak.loc[oar["FUEL"]].set_axis(oar["TECHNOLOGY"].to_numpy()).groupby(level=0).max()


def divide_af(base: pd.DataFrame, tech_peak: pd.DataFrame, years: list[str]) -> tuple[pd.DataFrame, int, int]:
    """AF' = AF / f: misma potencia de punta, misma energía anual que el 2 TS."""
    af = base[base["Parameter"] == "AvailabilityFactor"].copy()
    techs = tech_peak.index[(tech_peak > 1 + TOL).any(axis=1)]
    mask = af["TECHNOLOGY"].isin(techs)
    af.loc[mask, years] = af.loc[mask, years].astype(float).to_numpy() / tech_peak.loc[af.loc[mask, "TECHNOLOGY"]].to_numpy()
    missing = [t for t in techs if t not in set(af["TECHNOLOGY"])]
    region = base["REGION"].dropna().iloc[0]
    new = [_rows(base, "AvailabilityFactor", {"REGION": region, "TECHNOLOGY": t}, 1.0 / tech_peak.loc[t]) for t in missing]
    return pd.concat([af, pd.DataFrame(new, columns=base.columns)], ignore_index=True), int(mask.sum()), len(missing)


def run_cli_6ts_nest(
    description: str, base_sand: Path, out_dir: Path, out_prefix: str,
    prepare_base: Callable[[pd.DataFrame, list[str]], pd.DataFrame] | None = None,
) -> None:
    """CLI del 6 TS anidado. Cada escenario pasa su SAND base, salida y ``prepare_base`` propios."""
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--base", type=Path, default=base_sand)
    ap.add_argument("--shapes", type=Path, default=SHAPES_SAND)
    ap.add_argument("--flat", action="store_true", help="Formas planas dentro de cada bloque del 2 TS.")
    ap.add_argument("--af-div", action="store_true", help="AvailabilityFactor ÷ f en las tecnologías de uso final.")
    ap.add_argument("--free-shape", default="",
                    help="Prefijos (separados por coma) cuya energía anual se reparte con la forma de la UPME "
                         "sin respetar el día/noche del 2 TS, p. ej. PWRWND o PWRWND,PWRHYD.")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    free = tuple(p for p in args.free_shape.split(",") if p)
    suffix = "_FLAT" if args.flat else "_AF" if args.af_div else ""
    out = args.out or out_dir / f"{out_prefix}{suffix}.xlsx"
    if out.exists():
        raise SystemExit(f"{out} ya existe: no se sobrescribe.")

    base = read_sand(args.base)
    years = year_columns(base)
    if prepare_base is not None:
        base = prepare_base(base, years)
    shapes = clean_shapes(read_sand(args.shapes), years)
    blocks = build_nested(base, shapes, years, args.flat, free)
    nest_errors = check_nesting(base, blocks, years, free_shape=free)
    if free:
        print(f"Forma de la UPME (sin anidar) para: {', '.join(free)}")

    peak_blocks, peak_report = scale_peak_capacity(base, blocks, years, scale_costs=True)
    blocks.update(peak_blocks)
    if args.af_div:
        tech_peak = tech_peak_factors(base, blocks, years)
        blocks["AvailabilityFactor"], n_div, n_new = divide_af(base, tech_peak, years)
        print(f"AvailabilityFactor ÷ f: {n_div} filas divididas, {n_new} filas nuevas (AF = 1/f)")
    df = replace_params(base, blocks)
    errors = nest_errors + validate(df, years) + check_peak_capacity(df, years)

    ys = blocks["YearSplit"].set_index("TIMESLICE")["2030"].astype(float)
    sdp = blocks["SpecifiedDemandProfile"].groupby("TIMESLICE")["2030"].first()
    print("2030  TS   horas/año  demanda/promedio")
    for ts in NEW_TS:
        print(f"      {ts}  {ys[ts] * 8760:8.0f}  {sdp[ts] / ys[ts]:.4f}")
    print(f"Factor de uso final máx.: {peak_report['factor_max'].max():.4f}")
    print(peak_report[["parámetro", "tecnologías"]].to_string(index=False))
    if errors:
        print("VALIDACIÓN FALLIDA:")
        for e in errors[:30]:
            print(f"  - {e}")
        raise SystemExit(1)
    write_sand(df, out)
    print(f"Anidamiento y validación OK. SAND: {out} ({len(df)} filas)")

