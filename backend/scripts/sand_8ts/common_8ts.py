"""Método común para pasar un SAND de 2 timeslices a 8 TS (6 TS + bloque de punta corto).

Parte del 6 TS calibrado de ``scripts/sand_6ts/common.py`` (variante ``cal``) y
divide la tarde-noche de 7 h (S103/S203) en:
  - punta (S103/S203): ``--peak-hours`` h/día con demanda ``--peak-ratio`` × promedio;
  - resto (S104/S204): las horas restantes, con la energía que falta para
    conservar la del bloque de 7 h de la UPME.

El CF de ambos bloques es el del S103/S203 del 6 TS: la hidro **no** se realza
en la punta. Justamente se busca que el modelo vea que no puede seguirla. Ver
``docs/sand-8ts-punta.md``.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sand_6ts"))

from common import (  # noqa: E402
    INPUTS_DIR,
    OUTPUTS_DIR,
    RUNS_DIR,
    SHAPES_SAND,
    build_capacity_factor,
    build_demand_profile,
    build_year_split,
    check_peak_capacity,
    clean_shapes,
    fill_default_capacity_factor,
    read_sand,
    replace_params,
    scale_peak_capacity,
    validate,
    write_sand,
    year_columns,
)

__all__ = [
    "INPUTS_DIR", "OUTPUTS_DIR", "RUNS_DIR", "fill_default_capacity_factor", "run_cli_8ts", "split_peak_block",
]

EVENING_HOURS = 7  # tarde-noche del 6 TS de la UPME: 17–24 h
# Tarde-noche del 6 TS → (punta, resto) del 8 TS.
SPLIT = {"S103": ("S103", "S104"), "S203": ("S203", "S204")}
TOL = 1e-9


def _ts_order(ts: pd.Series) -> pd.Series:
    """Orden S101, S102, S103, S104, S201… dentro de cada grupo."""
    return ts.map(lambda t: (t[:2], int(t[2:])))


def _split_rows(block: pd.DataFrame, years: list[str], values: Callable) -> pd.DataFrame:
    """Reemplaza cada fila de S103/S203 por sus filas de punta y resto.

    ``values(row, part)`` devuelve los valores por año de la parte
    (``"peak"`` o ``"rest"``). Se conserva el orden original de las filas.
    """
    out = []
    for pos, (_, row) in enumerate(block.iterrows()):
        if row["TIMESLICE"] not in SPLIT:
            out.append((pos, row))
            continue
        for part, ts in zip(("peak", "rest"), SPLIT[row["TIMESLICE"]]):
            new = row.copy()
            new["TIMESLICE"] = ts
            new[years] = values(row, part)
            out.append((pos, new))
    df = pd.DataFrame([r for _, r in out], columns=block.columns)
    df["_pos"] = [p for p, _ in out]
    df["_ts"] = _ts_order(df["TIMESLICE"])
    return df.sort_values(["_pos", "_ts"], kind="stable").drop(columns=["_pos", "_ts"]).reset_index(drop=True)


def split_peak_block(
    blocks: dict[str, pd.DataFrame], years: list[str], hours: float = 3, ratio: float = 1.30
) -> dict[str, pd.DataFrame]:
    """Divide la tarde-noche (S103/S203) del 6 TS en punta y resto.

    - YearSplit: punta = hours/7 del bloque, resto = el resto.
    - SpecifiedDemandProfile: punta = ratio · YearSplit_punta; resto = SDP_6TS − punta
      (cada perfil sigue sumando 1 y la tarde-noche conserva su energía).
    - CapacityFactor: punta y resto repiten el CF del bloque (energía anual igual).
    """
    if not 0 < hours < EVENING_HOURS:
        raise ValueError(f"--peak-hours debe estar entre 0 y {EVENING_HOURS}.")
    share = {"peak": hours / EVENING_HOURS, "rest": 1 - hours / EVENING_HOURS}
    ys6 = blocks["YearSplit"].set_index("TIMESLICE")[years].astype(float)

    ys = _split_rows(blocks["YearSplit"], years, lambda r, part: r[years].astype(float) * share[part])

    def sdp_values(row: pd.Series, part: str) -> pd.Series:
        peak = ratio * ys6.loc[row["TIMESLICE"]] * share["peak"]
        if part == "peak":
            return peak
        rest = row[years].astype(float) - peak
        if (rest <= TOL).any():
            raise ValueError(
                f"--peak-ratio {ratio} con {hours} h deja sin demanda el resto de {row['TIMESLICE']} "
                f"({row['FUEL']}).")
        return rest

    sdp = _split_rows(blocks["SpecifiedDemandProfile"], years, sdp_values)
    cf = _split_rows(blocks["CapacityFactor"], years, lambda r, part: r[years])
    return {"YearSplit": ys, "SpecifiedDemandProfile": sdp, "CapacityFactor": cf}


def check_split(six: dict[str, pd.DataFrame], eight: dict[str, pd.DataFrame], years: list[str]) -> list[str]:
    """Punta + resto = tarde-noche del 6 TS (YearSplit y SDP), y CF de ambos = CF del 6 TS."""
    errors = []
    for param, key in (("YearSplit", []), ("SpecifiedDemandProfile", ["FUEL"]), ("CapacityFactor", ["TECHNOLOGY"])):
        b6 = six[param][six[param]["TIMESLICE"].isin(SPLIT)]
        b8 = eight[param]
        for evening, (peak, rest) in SPLIT.items():
            ref = b6[b6["TIMESLICE"] == evening].set_index(key or "TIMESLICE")[years].astype(float)
            p = b8[b8["TIMESLICE"] == peak].set_index(key or "TIMESLICE")[years].astype(float)
            r = b8[b8["TIMESLICE"] == rest].set_index(key or "TIMESLICE")[years].astype(float)
            if not key:
                p.index = r.index = ref.index
            if param == "CapacityFactor":
                bad = (p - ref).abs().to_numpy().max() > TOL or (r - ref).abs().to_numpy().max() > TOL
            else:
                bad = (p + r - ref).abs().to_numpy().max() > TOL
            if bad:
                errors.append(f"{param}: {peak}/{rest} no reproducen {evening} del 6 TS.")
    return errors


def run_cli_8ts(
    description: str,
    base_sand: Path,
    out_dir: Path,
    out_prefix: str,
    prepare_base: Callable[[pd.DataFrame, list[str]], pd.DataFrame] | None = None,
) -> None:
    """CLI común de 8 TS. Cada escenario pasa su SAND base, salida y ajustes propios."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--base", type=Path, default=base_sand)
    parser.add_argument("--shapes", type=Path, default=SHAPES_SAND)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--peak-hours", type=float, default=3,
                        help="Horas/día del bloque de punta dentro de la tarde-noche de 7 h (default 3).")
    parser.add_argument("--peak-ratio", type=float, default=1.30,
                        help="Demanda de la punta = ratio × promedio (default 1,30).")
    args = parser.parse_args()

    base = read_sand(args.base)
    years = year_columns(base)
    if prepare_base is not None:
        base = prepare_base(base, years)
    shapes = clean_shapes(read_sand(args.shapes), years)

    cf, report = build_capacity_factor(base, shapes, years)
    six = {
        "YearSplit": build_year_split(shapes, base),
        "SpecifiedDemandProfile": build_demand_profile(base, shapes, years),
        "CapacityFactor": cf,
    }
    blocks = split_peak_block(six, years, args.peak_hours, args.peak_ratio)
    peak_blocks, peak_report = scale_peak_capacity(base, blocks, years)
    blocks.update(peak_blocks)

    df = replace_params(base, blocks)
    errors = validate(df, years) + check_peak_capacity(df, years) + check_split(six, blocks, years)

    tag = f"CAL_PB{args.peak_hours:g}H{round(args.peak_ratio * 100)}"
    out = args.out or out_dir / f"{out_prefix}_{tag}.xlsx"
    ys = blocks["YearSplit"].set_index("TIMESLICE")["2030"].astype(float)
    sdp = blocks["SpecifiedDemandProfile"]
    sdp = sdp[sdp["FUEL"] == sdp["FUEL"].iloc[0]].set_index("TIMESLICE")["2030"].astype(float)
    print(f"Base:   {args.base.name} ({len(base)} filas)")
    print(f"Formas: {args.shapes.name}")
    print("\nTimeslices 2030 (horas/año, demanda/promedio):")
    print(pd.DataFrame({"horas": (ys * 8760).round(0), "SDP/YS": (sdp / ys).round(3)}).to_string())
    print(f"\nMáx. diferencia de energía anual vs 2TS: {report['max_dif_energia'].max():.2e}")
    print(f"Topes de capacidad escalados por punta (factor máx. {peak_report['factor_max'].max():.4f}):")
    print(peak_report[["parámetro", "tecnologías"]].to_string(index=False))
    if errors:
        print("\nVALIDACIÓN FALLIDA:")
        for e in errors:
            print(f"  - {e}")
        raise SystemExit(1)
    write_sand(df, out)
    print(f"\nValidación OK. SAND: {out} ({len(df)} filas)")

