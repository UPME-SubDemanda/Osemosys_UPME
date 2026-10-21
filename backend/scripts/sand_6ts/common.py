"""Método común para pasar un SAND de 2 timeslices a 6 TS.

Lo usan los scripts de cada escenario (``build_pd_6ts.py``, ``build_pa_6ts.py``…),
que solo definen su SAND base, el nombre de salida y sus ajustes propios.
Formas: ``tmp/sand/inputs/6TS_parameters_SAND.xlsx`` (entregado por la UPME; solo 6
parámetros). Ver ``docs/sand-6ts-migracion.md``.

Variantes:
  - ``cal`` (default): del 6 TS se toman solo YearSplit y las formas
    (SpecifiedDemandProfile y CapacityFactor de solar/eólica/hidro). Los CF se
    calibran para que cada tecnología conserve la energía anual del 2 TS:
    CF_ts = min(1, L · forma_ts / Σ forma·YearSplit), con L = Σ CF_2TS·YearSplit_2TS.
    AvailabilityFactor y demandas quedan como en el 2 TS.
  - ``upme``: los 6 parámetros del archivo de la UPME reemplazan a los del
    2 TS, corrigiendo solo el armado (2055 vacío, PWRFOIL, GRDDSTELC). Sirve
    para documentar la doble reducción AF × CF.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
# Los SAND no se versionan: viven en tmp/sand/ (ignorado por git).
WORK_DIR = REPO_ROOT / "tmp" / "sand"
INPUTS_DIR = WORK_DIR / "inputs"    # SAND base y formas entregados por la UPME
OUTPUTS_DIR = WORK_DIR / "outputs"  # SAND generados (entregables y variantes)
RUNS_DIR = WORK_DIR / "runs"        # corridas de run_osemosys_cli.py y sus logs
SHAPES_SAND = INPUTS_DIR / "6TS_parameters_SAND.xlsx"

TS_PARAMS = ["YearSplit", "SpecifiedDemandProfile", "CapacityFactor"]
UPME_PARAMS = TS_PARAMS + ["AvailabilityFactor", "AccumulatedAnnualDemand", "SpecifiedAnnualDemand"]

# Correspondencia 2 TS → 6 TS (madrugada 6 h / día 11 h / tarde-noche 7 h).
DAY_2TS, NIGHT_2TS = "S101", "S102"
DAY_6TS = ["S102", "S202"]

# Errores de armado del archivo de la UPME.
TECH_RENAMES = {"PWRFOIL": "PWRFOL"}
TECH_DROPS = {"GRDDSTELC"}

TOL = 1e-9
SCALAR_COLUMN = "Time indipendent variables"  # así se llama en el SAND (sic)

# Parámetros de capacidad que se escalan por el factor de punta de la demanda.
# TotalAnnualMinCapacityInvestment no se escala: subirlo obligaría a invertir más.
PEAK_CAPACITY_PARAMS = [
    "ResidualCapacity", "TotalAnnualMaxCapacityInvestment", "TotalAnnualMaxCapacity",
    "TotalAnnualMinCapacity",
]
CAPACITY_SENTINEL = 99_999  # valores ≥ esto significan "sin límite"
# Costos por unidad de capacidad que se dividen por el mismo factor (costo por energía igual al 2 TS).
PEAK_COST_PARAMS = ["CapitalCost", "FixedCost"]
COST_SENTINEL = 999_999  # costos ≥ esto son "prohibitivos": se dejan igual

HYDRO_PREFIX = "PWRHYD"  # embalse, filo de agua y filo de agua NDC

# Tarde-noche (7 h) de cada semestre: el bloque de punta para --peak-ratio.
EVENING_6TS = ["S103", "S203"]


def read_sand(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Parameters")
    df.columns = [str(c) for c in df.columns]
    return df


def year_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.isdigit()]


def fill_default_capacity_factor(base: pd.DataFrame, years: list[str]) -> pd.DataFrame:
    """Completa los CF omitidos con el default de OSeMOSYS (1).

    Los SAND exportados desde la BD de la app (``*_scenario_<id>_Parameters_SAND``)
    son dispersos: si el CF vale 1 en un TS, la fila no viene. Sin completar,
    el nivel anual L de esas tecnologías saldría a la mitad. Se pasa como
    ``prepare_base`` en los escenarios que parten de un export de la BD.
    """
    cf = base[base["Parameter"] == "CapacityFactor"]
    timeslices = base.loc[base["Parameter"] == "YearSplit", "TIMESLICE"].unique()
    have = set(zip(cf["REGION"], cf["TECHNOLOGY"], cf["TIMESLICE"]))
    rows = [
        _rows(base, "CapacityFactor", {"REGION": r, "TECHNOLOGY": t, "TIMESLICE": ts},
              pd.Series(1.0, index=years))
        for r, t in cf[["REGION", "TECHNOLOGY"]].drop_duplicates().itertuples(index=False)
        for ts in timeslices if (r, t, ts) not in have
    ]
    if not rows:
        return base
    print(f"CapacityFactor: {len(rows)} filas omitidas completadas con 1 (export disperso de la BD).")
    filled = pd.concat([cf, pd.DataFrame(rows, columns=base.columns)], ignore_index=True)
    return replace_params(base, {"CapacityFactor": filled})


def clean_shapes(shapes: pd.DataFrame, years: list[str]) -> pd.DataFrame:
    """Corrige el armado del archivo de 6 TS: años vacíos y nombres de tecnología."""
    shapes = shapes.copy()
    for i, y in enumerate(years):  # años vacíos (2055) = año anterior
        if shapes[y].isna().all() and i > 0:
            shapes[y] = shapes[years[i - 1]]
    shapes["TECHNOLOGY"] = shapes["TECHNOLOGY"].replace(TECH_RENAMES)
    return shapes[~shapes["TECHNOLOGY"].isin(TECH_DROPS)].reset_index(drop=True)


def _rows(template: pd.DataFrame, param: str, keys: dict, values: pd.Series) -> dict:
    row = dict.fromkeys(template.columns)
    row["Parameter"] = param
    row["REGION"] = keys.pop("REGION")
    row.update(keys)
    row.update(values.to_dict())
    return row


def build_year_split(shapes: pd.DataFrame, base: pd.DataFrame) -> pd.DataFrame:
    """YearSplit del 6 TS con la convención del 2 TS (sin REGION si el base no la trae)."""
    ys = shapes[shapes["Parameter"] == "YearSplit"].reset_index(drop=True)
    if base.loc[base["Parameter"] == "YearSplit", "REGION"].isna().all():
        ys["REGION"] = None
    return ys


def reshape_peak(common: pd.DataFrame, ys: pd.DataFrame, ratio: float) -> pd.DataFrame:
    """Fija la tarde-noche en ``ratio`` veces el promedio (SDP = ratio · YearSplit).

    Conserva la participación de cada semestre del perfil de la UPME; el resto
    del semestre se reparte entre madrugada y día en su proporción original.
    """
    out = common.copy()
    for evening in EVENING_6TS:
        season = [ts for ts in common.index if ts[:2] == evening[:2]]
        others = [ts for ts in season if ts != evening]
        total = common.loc[season].sum()
        out.loc[evening] = ratio * ys.loc[evening]
        rest = total - out.loc[evening]
        if (rest <= 0).any():
            raise ValueError(f"--peak-ratio {ratio} deja sin demanda al resto del semestre {evening[:2]}.")
        out.loc[others] = common.loc[others] / common.loc[others].sum() * rest
    return out


def build_demand_profile(
    base: pd.DataFrame, shapes: pd.DataFrame, years: list[str], peak_ratio: float | None = None
) -> pd.DataFrame:
    """Aplica el perfil común del 6 TS a todos los fuels con perfil en el 2 TS."""
    sdp6 = shapes[shapes["Parameter"] == "SpecifiedDemandProfile"]
    profiles = sdp6.groupby("TIMESLICE")[years]
    if (profiles.max() - profiles.min()).abs().to_numpy().max() > TOL:
        raise ValueError("Los perfiles de demanda del 6 TS no son idénticos entre fuels.")
    common = profiles.mean()
    if peak_ratio is not None:
        ys = shapes[shapes["Parameter"] == "YearSplit"].set_index("TIMESLICE")[years]
        common = reshape_peak(common, ys, peak_ratio)

    sdp2 = base[base["Parameter"] == "SpecifiedDemandProfile"]
    rows = []
    for (region, fuel), _ in sdp2.groupby(["REGION", "FUEL"], sort=False):
        for ts in common.index:
            rows.append(_rows(base, "SpecifiedDemandProfile",
                              {"REGION": region, "FUEL": fuel, "TIMESLICE": ts}, common.loc[ts]))
    return pd.DataFrame(rows, columns=base.columns)


def build_capacity_factor(
    base: pd.DataFrame, shapes: pd.DataFrame, years: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """CF de 6 TS calibrados a la energía anual del 2 TS. Devuelve (filas, reporte)."""
    ys2 = base[base["Parameter"] == "YearSplit"].set_index("TIMESLICE")[years]
    ys6 = shapes[shapes["Parameter"] == "YearSplit"].set_index("TIMESLICE")[years]
    cf2 = base[base["Parameter"] == "CapacityFactor"]
    cf6 = shapes[shapes["Parameter"] == "CapacityFactor"]

    rows, report = [], []
    for (region, tech), g in cf2.groupby(["REGION", "TECHNOLOGY"], sort=False):
        by_ts = g.set_index("TIMESLICE")[years]
        level = (by_ts * ys2.loc[by_ts.index]).sum()  # L por año

        s6 = cf6[(cf6["REGION"] == region) & (cf6["TECHNOLOGY"] == tech)]
        if not s6.empty:
            shape, source = s6.set_index("TIMESLICE")[years], "forma 6TS"
        elif (by_ts.max() - by_ts.min()).abs().max() > TOL:
            shape = pd.DataFrame(
                {ts: by_ts.loc[DAY_2TS if ts in DAY_6TS else NIGHT_2TS] for ts in ys6.index}
            ).T
            source = "día/noche 2TS"
        else:
            shape, source = None, "plano"

        if shape is None:
            new = pd.DataFrame({ts: by_ts.iloc[0] for ts in ys6.index}).T
        else:
            mean = (shape * ys6.loc[shape.index]).sum()
            scale = level.div(mean.where(mean > 0), fill_value=np.nan).fillna(0.0)
            new = shape.mul(scale, axis=1).clip(upper=1.0)
        new = new.loc[ys6.index]

        energy = (new * ys6).sum()
        report.append({
            "TECHNOLOGY": tech, "fuente": source,
            "L_2030": level["2030"], "L_2055": level["2055"],
            "max_dif_energia": (energy - level).abs().max(),
            "CF_max": new.to_numpy().max(),
        })
        for ts in new.index:
            rows.append(_rows(base, "CapacityFactor",
                              {"REGION": region, "TECHNOLOGY": tech, "TIMESLICE": ts}, new.loc[ts]))
    return pd.DataFrame(rows, columns=base.columns), pd.DataFrame(report)


def scale_peak_capacity(
    base: pd.DataFrame, blocks: dict[str, pd.DataFrame], years: list[str], scale_costs: bool = True
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Escala los topes de capacidad de las tecnologías que abastecen demandas con perfil.

    En el SAND, las tecnologías de demanda tienen ResidualCapacity = demanda anual,
    CF = 1, e inversión anual limitada: sus topes alcanzan justo para una carga
    plana. Con un perfil cuya punta supera el promedio (SDP/YearSplit > 1) el
    modelo es infactible (p. ej. TERCLIM_SPL en 2053–2055 por el tope de inversión
    acumulado en la vida útil). Se multiplican ResidualCapacity,
    TotalAnnualMaxCapacityInvestment y TotalAnnualMaxCapacity (si es finita) por el
    factor de punta f = max_ts(SDP/YearSplit) del fuel que producen (el mayor si
    producen varios). Los límites de actividad (energía anual) no cambian.
    """
    ys = blocks["YearSplit"].set_index("TIMESLICE")[years]
    sdp = blocks["SpecifiedDemandProfile"]
    ratio = sdp[years].to_numpy() / ys.loc[sdp["TIMESLICE"]].to_numpy()
    peak = (
        pd.DataFrame(ratio, columns=years, index=sdp["FUEL"].to_numpy())
        .groupby(level=0).max().clip(lower=1.0)
    )
    oar = base[(base["Parameter"] == "OutputActivityRatio") & base["FUEL"].isin(peak.index)]
    oar = oar[(oar[years] > 0).any(axis=1)]
    tech_peak = (
        peak.loc[oar["FUEL"]].set_axis(oar["TECHNOLOGY"].to_numpy()).groupby(level=0).max()
    )

    blocks_out, report = {}, []
    for param in PEAK_CAPACITY_PARAMS:
        block = base[base["Parameter"] == param].copy()
        values = block[years]
        # Los centinelas (99999, 999999…) significan "sin límite": no se escalan.
        finite = values.where((values > 0) & (values < CAPACITY_SENTINEL))
        mask = block["TECHNOLOGY"].isin(tech_peak.index) & finite.notna().any(axis=1)
        factors = tech_peak.loc[block.loc[mask, "TECHNOLOGY"]].to_numpy()
        scaled = finite.loc[mask].to_numpy() * factors
        block.loc[mask, years] = np.where(np.isnan(scaled), values.loc[mask].to_numpy(), scaled)
        blocks_out[param] = block
        report.append({"parámetro": param, "tecnologías": int(mask.sum())})

    # Cambio de unidad de capacidad (×f): el costo por unidad se divide por f para
    # que el costo por energía anual sea el mismo del 2 TS.
    for param in PEAK_COST_PARAMS if scale_costs else []:
        block = base[base["Parameter"] == param].copy()
        values = block[years]
        priced = values.where((values > 0) & (values < COST_SENTINEL))
        mask = block["TECHNOLOGY"].isin(tech_peak.index) & priced.notna().any(axis=1)
        factors = tech_peak.loc[block.loc[mask, "TECHNOLOGY"]].to_numpy()
        scaled = priced.loc[mask].to_numpy() / factors
        block.loc[mask, years] = np.where(np.isnan(scaled), values.loc[mask].to_numpy(), scaled)
        blocks_out[param] = block
        report.append({"parámetro": f"{param} (÷f)", "tecnologías": int(mask.sum())})

    rc = blocks_out["ResidualCapacity"].set_index("TECHNOLOGY")[years]
    max_cap = blocks_out["TotalAnnualMaxCapacity"].set_index("TECHNOLOGY")[years]
    over = rc.gt(max_cap.reindex(rc.index)).any(axis=1)
    if over.any():
        raise ValueError(f"ResidualCapacity escalada supera TotalAnnualMaxCapacity: {over[over].index.tolist()}")

    report = pd.DataFrame(report)
    report["factor_max"] = float(tech_peak.to_numpy().max())
    return blocks_out, report


def apply_dry_years(
    cf: pd.DataFrame, base: pd.DataFrame, years: list[str], factor: float, dry_years: list[str]
) -> pd.DataFrame:
    """Año seco: CF de las tecnologías hidro × factor en los años indicados (todos los TS).

    No se permite en años con generación hidro mínima obligatoria
    (TotalTechnologyAnnualActivityLowerLimit > 0), porque sería infactible.
    """
    bad = [y for y in dry_years if y not in years]
    if bad:
        raise ValueError(f"Años secos fuera del horizonte: {bad}")
    hydro = cf["TECHNOLOGY"].str.startswith(HYDRO_PREFIX)
    ll = base[(base["Parameter"] == "TotalTechnologyAnnualActivityLowerLimit")
              & base["TECHNOLOGY"].str.startswith(HYDRO_PREFIX, na=False)]
    forced = [y for y in dry_years if (ll[y] > 0).any()]
    if forced:
        raise ValueError(f"La hidro tiene generación mínima obligatoria en {forced}; elige años sin ese límite.")
    cf = cf.copy()
    cf.loc[hydro, dry_years] = cf.loc[hydro, dry_years].astype(float) * factor
    techs = sorted(cf.loc[hydro, "TECHNOLOGY"].unique())
    print(f"Año seco: CF × {factor} en {', '.join(dry_years)} para {', '.join(techs)}")
    return cf


def replace_params(base: pd.DataFrame, new_blocks: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Reemplaza bloques de parámetros conservando el orden original del SAND."""
    order = list(dict.fromkeys(base["Parameter"]))
    order += [p for p in new_blocks if p not in order]
    parts = [
        new_blocks[p][base.columns] if p in new_blocks else base[base["Parameter"] == p]
        for p in order
    ]
    return pd.concat(parts, ignore_index=True)


def validate(df: pd.DataFrame, years: list[str]) -> list[str]:
    errors = []
    ys = df[df["Parameter"] == "YearSplit"][years]
    if ((ys.sum() - 1).abs() > 1e-6).any():
        errors.append("YearSplit no suma 1 en algún año.")
    sdp = df[df["Parameter"] == "SpecifiedDemandProfile"].groupby("FUEL")[years].sum()
    if ((sdp - 1).abs() > 1e-6).any().any():
        errors.append(f"SpecifiedDemandProfile no suma 1: {sdp.index[((sdp - 1).abs() > 1e-6).any(axis=1)].tolist()}")
    cf = df[df["Parameter"] == "CapacityFactor"][years]
    if (cf < -TOL).any().any() or (cf > 1 + TOL).any().any():
        errors.append("CapacityFactor fuera de [0, 1].")
    n_ts = df[df["Parameter"] == "YearSplit"]["TIMESLICE"].nunique()
    for p in TS_PARAMS:
        block = df[df["Parameter"] == p]
        if block[years].isna().any().any():
            errors.append(f"{p} tiene celdas vacías.")
        key = "FUEL" if p == "SpecifiedDemandProfile" else "TECHNOLOGY" if p == "CapacityFactor" else None
        if key and (block.groupby(key)["TIMESLICE"].nunique() != n_ts).any():
            errors.append(f"{p}: hay {key}s sin los {n_ts} timeslices.")
    return errors


def check_peak_capacity(df: pd.DataFrame, years: list[str]) -> list[str]:
    """Verifica que cada demanda con perfil pueda cubrirse en su TS de punta.

    Capacidad alcanzable por tecnología y año: min(TotalAnnualMaxCapacity,
    ResidualCapacity + inversión máxima de los años dentro de la vida útil),
    por OutputActivityRatio y por el CF del TS. Sirve para detectar antes de
    resolver los topes dimensionados para carga plana.
    """
    def table(param: str) -> pd.DataFrame:
        return df[df["Parameter"] == param].groupby("TECHNOLOGY")[years].first()

    rc, inv, max_cap = table("ResidualCapacity"), table("TotalAnnualMaxCapacityInvestment"), table("TotalAnnualMaxCapacity")
    life = df[df["Parameter"] == "OperationalLife"].set_index("TECHNOLOGY")["Time indipendent variables"]
    cf = df[df["Parameter"] == "CapacityFactor"].set_index(["TECHNOLOGY", "TIMESLICE"])[years]
    ys = df[df["Parameter"] == "YearSplit"].set_index("TIMESLICE")[years]
    sdp = df[df["Parameter"] == "SpecifiedDemandProfile"]
    sad = df[df["Parameter"] == "SpecifiedAnnualDemand"].set_index("FUEL")[years]
    oar = df[(df["Parameter"] == "OutputActivityRatio") & (df[years] > 0).any(axis=1)]
    yrs = np.array([int(y) for y in years])

    reachable = {}
    for tech in oar.loc[oar["FUEL"].isin(sdp["FUEL"]), "TECHNOLOGY"].unique():
        alive = (yrs[:, None] - yrs[None, :] >= 0) & (yrs[:, None] - yrs[None, :] < life.get(tech, 1))
        new = alive @ inv.loc[tech].to_numpy()
        reachable[tech] = np.minimum(max_cap.loc[tech].to_numpy(), rc.loc[tech].to_numpy() + new)

    def cf_of(tech: str, ts: str) -> np.ndarray:
        # Sin fila de CF → default de OSeMOSYS (1).
        return cf.loc[(tech, ts)].to_numpy() if (tech, ts) in cf.index else np.ones(len(years))

    errors = []
    for fuel, prof in sdp.groupby("FUEL"):
        need = sad.loc[fuel].to_numpy() * prof.set_index("TIMESLICE")[years]  # energía por TS
        supply = oar[oar["FUEL"] == fuel]
        for ts in need.index:
            cap = sum(
                reachable[r.TECHNOLOGY] * cf_of(r.TECHNOLOGY, ts)
                * r[years].to_numpy(dtype=float) * ys.loc[ts].to_numpy()
                for _, r in supply.iterrows()
            )
            gap = need.loc[ts].to_numpy() - cap
            if (gap > 1e-7).any():
                bad = [y for y, g in zip(years, gap) if g > 1e-7]
                errors.append(f"{fuel} no cubre la punta en {ts} ({bad[0]}–{bad[-1]}, falta máx. {gap.max():.4g} PJ)")
                break
    return errors


def write_sand(df: pd.DataFrame, path: Path) -> None:
    """Escribe con el mismo formato del SAND de la UPME.

    Encabezados de año como texto ("2022"), valores numéricos como float y
    MODE_OF_OPERATION como texto ("1"), igual que el PD de 2 TS, para que el
    importador de la app lo trate igual.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    numeric = [c for c in out.columns if str(c).isdigit()] + [SCALAR_COLUMN]
    out[numeric] = out[numeric].astype(float)
    mode = out["MODE_OF_OPERATION"]
    out["MODE_OF_OPERATION"] = mode.map(lambda v: None if pd.isna(v) else str(int(float(v))))
    out = out.astype(object).where(out.notna(), None)
    out.to_excel(path, sheet_name="Parameters", index=False)



def run_cli(
    description: str,
    base_sand: Path,
    out_dir: Path,
    out_prefix: str,
    prepare_base: Callable[[pd.DataFrame, list[str]], pd.DataFrame] | None = None,
) -> None:
    """CLI común. Cada escenario pasa su SAND base, salida y ajustes propios.

    ``prepare_base(base, years)`` corrige el SAND base antes de construir el
    6 TS (p. ej. completar valores omitidos en un export de la BD).
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--variant", choices=["cal", "upme"], default="cal")
    parser.add_argument("--base", type=Path, default=base_sand)
    parser.add_argument("--shapes", type=Path, default=SHAPES_SAND)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--no-peak-capacity", action="store_true",
                        help="No escalar la capacidad de las tecnologías de demanda por la punta.")
    parser.add_argument("--no-cost-scaling", action="store_true",
                        help="Escalar la capacidad por la punta sin dividir CapitalCost y FixedCost por f.")
    parser.add_argument("--peak-ratio", type=float, default=None,
                        help="Tarde-noche (S103/S203) = ratio × promedio. Default: perfil de la UPME (≈1,077).")
    parser.add_argument("--hydro-dry", type=float, default=None,
                        help="Año seco: multiplica el CF hidro (todos los TS) por este factor en --dry-years.")
    parser.add_argument("--dry-years", type=lambda s: [y.strip() for y in s.split(",")], default=[],
                        help="Años secos separados por coma, p. ej. 2030 o 2027,2031.")
    args = parser.parse_args()
    if args.peak_ratio is not None and args.variant != "cal":
        parser.error("--peak-ratio solo aplica a la variante cal.")
    if (args.hydro_dry is None) != (not args.dry_years):
        parser.error("--hydro-dry y --dry-years van juntos.")

    base = read_sand(args.base)
    years = year_columns(base)
    if prepare_base is not None:
        base = prepare_base(base, years)
    shapes = clean_shapes(read_sand(args.shapes), years)

    if args.variant == "cal":
        cf, report = build_capacity_factor(base, shapes, years)
        blocks = {
            "YearSplit": build_year_split(shapes, base),
            "SpecifiedDemandProfile": build_demand_profile(base, shapes, years, args.peak_ratio),
            "CapacityFactor": cf,
        }
    else:
        blocks = {p: shapes[shapes["Parameter"] == p] for p in UPME_PARAMS}
        # Tecnologías sin CF en el archivo de la UPME: CF = 1 explícito en los 6 TS.
        ys6 = blocks["YearSplit"]
        cf = blocks["CapacityFactor"]
        rows = [
            _rows(base, "CapacityFactor", {"REGION": r, "TECHNOLOGY": t, "TIMESLICE": ts},
                  pd.Series(1.0, index=years))
            for r, t in base[base["Parameter"] == "CapacityFactor"][["REGION", "TECHNOLOGY"]]
            .drop_duplicates().itertuples(index=False)
            if t not in set(cf["TECHNOLOGY"])
            for ts in ys6["TIMESLICE"]
        ]
        blocks["CapacityFactor"] = pd.concat([cf, pd.DataFrame(rows, columns=base.columns)], ignore_index=True)
        report = None

    if args.hydro_dry is not None:
        blocks["CapacityFactor"] = apply_dry_years(
            blocks["CapacityFactor"], base, years, args.hydro_dry, args.dry_years)

    peak_report = None
    if not args.no_peak_capacity:
        peak_blocks, peak_report = scale_peak_capacity(base, blocks, years, not args.no_cost_scaling)
        blocks.update(peak_blocks)

    df = replace_params(base, blocks)
    errors = validate(df, years) + check_peak_capacity(df, years)

    tag = args.variant.upper() + (f"_P{round(args.peak_ratio * 100)}" if args.peak_ratio else "")
    if args.no_cost_scaling:
        tag += "_SINDIV"
    if args.hydro_dry is not None:
        tag += f"_SECO{round(args.hydro_dry * 100)}_{'-'.join(args.dry_years)}"
    out = args.out or out_dir / f"{out_prefix}_{tag}.xlsx"
    print(f"Base:   {args.base.name} ({len(base)} filas)")
    print(f"Formas: {args.shapes.name}")
    for p in UPME_PARAMS:
        print(f"  {p:<26} 2TS {int((base['Parameter'] == p).sum()):>4} → 6TS {int((df['Parameter'] == p).sum()):>4}")
    if report is not None:
        pd.set_option("display.width", 200)
        moved = report[report["fuente"] != "plano"]
        print("\nCapacityFactor calibrado (tecnologías con forma):")
        print(moved.round(4).to_string(index=False))
        print(f"\nMáx. diferencia de energía anual vs 2TS: {report['max_dif_energia'].max():.2e}")
    if peak_report is not None:
        print(f"\nTopes de capacidad escalados por punta (factor máx. {peak_report['factor_max'].max():.4f}):")
        print(peak_report[["parámetro", "tecnologías"]].to_string(index=False))
    if errors:
        print("\nVALIDACIÓN FALLIDA:")
        for e in errors:
            print(f"  - {e}")
        raise SystemExit(1)
    write_sand(df, out)
    print(f"\nValidación OK. SAND: {out} ({len(df)} filas)")
