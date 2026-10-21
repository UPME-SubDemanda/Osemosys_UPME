"""Genera el reporte HTML compacto que compara PD, PA y CN con 2, 6 y 8 TS.

Muestra las corridas (costo total y del sector eléctrico), la capacidad
eléctrica instalada por familia y el perfil diario de generación por bloque.
Lee las corridas de ``tmp/sand/runs/<carpeta>/`` y el SAND de cada una desde su log.

Uso (desde backend/):
  python scripts/sand_8ts/report_8ts_html.py
  python scripts/sand_8ts/report_8ts_html.py --pa8 PA_8TS_PB3H130_IPM   # PA 8 TS con IPM
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sand_6ts"))

from common import RUNS_DIR  # noqa: E402
from report_6ts_html import PJ_PER_GW_YEAR, family, generated_at, run_info  # noqa: E402

TEMPLATE = Path(__file__).with_name("report_8ts_template.html")

# (escenario, resolución, carpeta de la corrida); PA 8 TS se puede cambiar con --pa8.
CASES = [
    ("PD", "2TS", "2TS"), ("PD", "6TS", "6TS_v19oct"), ("PD", "8TS", "8TS_PB3H130"),
    ("PA", "2TS", "PA_2TS"), ("PA", "6TS", "PA_6TS"), ("PA", "8TS", "PA_8TS_PB3H130"),
    ("CN", "2TS", "CN_2TS"), ("CN", "6TS", "CN_6TS"), ("CN", "8TS", "CN_8TS_PB3H130"),
]
YEARS = [2030, 2040, 2055]
DISPATCH_YEARS = [2026, 2030, 2040, 2055]
HOURS = 8760
CAP_FAMILIES = ["Hidro", "Solar", "Eólica", "Gas", "Carbón", "Nuclear", "Geotermia", "Otras"]
# Grupos del perfil diario: el gas va aparte porque es el que cubre la punta en 8 TS.
DISPATCH_GROUPS = {"Hidro": ["Hidro"], "Solar": ["Solar"], "Eólica": ["Eólica"], "Gas": ["Gas"],
                   "Otras": ["Carbón", "Nuclear", "Geotermia", "Otras"]}


def pwr_cost(folder: str) -> float:
    d = pd.read_csv(RUNS_DIR / folder / "TotalDiscountedCostByTechnology.csv")
    return float(d.loc[d["IDX2"].str.startswith("PWR"), "VALUE"].sum())


def capacity(folder: str) -> dict:
    """Capacidad eléctrica (GW) por familia en YEARS."""
    cap = pd.read_csv(RUNS_DIR / folder / "TotalCapacityAnnual.csv")
    cap["F"] = cap["TECHNOLOGY"].map(family)
    gw = cap.dropna(subset=["F"]).groupby(["F", "YEAR"])["VALUE"].sum().div(PJ_PER_GW_YEAR)
    gw = gw.unstack("YEAR").reindex(index=CAP_FAMILIES, columns=YEARS).fillna(0.0)
    return {f: [round(float(v), 3) for v in gw.loc[f]] for f in CAP_FAMILIES}


def dispatch(folder: str, sand: pd.DataFrame) -> dict:
    """Potencia media (GW) por grupo y TS para cada año de DISPATCH_YEARS."""
    prod = pd.read_csv(RUNS_DIR / folder / "ProductionByTechnology.csv").rename(columns={"DUMMY": "TS"})
    prod["F"] = prod["TECHNOLOGY"].map(family)
    prod = prod.dropna(subset=["F"])
    to_group = {f: g for g, fams in DISPATCH_GROUPS.items() for f in fams}
    prod["G"] = prod["F"].map(to_group)
    ys = sand[sand["Parameter"] == "YearSplit"].set_index("TIMESLICE")
    out = {}
    for year in DISPATCH_YEARS:
        p = prod[prod["YEAR"] == year].groupby(["G", "TS"])["VALUE"].sum().unstack("TS").fillna(0.0)
        hours = ys[str(year)].astype(float) * HOURS
        gw = p.div(hours.reindex(p.columns) * 3.6e-3, axis=1)  # PJ / (h · 0,0036 PJ/GWh)
        out[year] = {g: {ts: round(float(gw.loc[g, ts]), 3) for ts in gw.columns} if g in gw.index else {}
                     for g in DISPATCH_GROUPS}
    return out


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pa8", default="PA_8TS_PB3H130", help="Carpeta de la corrida PA 8 TS.")
    parser.add_argument("--out", type=Path, default=RUNS_DIR / "report" / "comparacion-2-6-8ts.html")
    args = parser.parse_args()

    runs, cap, disp = [], {}, {}
    for scen, ts, folder in CASES:
        if (scen, ts) == ("PA", "8TS"):
            folder = args.pa8
        info, sand = run_info(scen, ts, folder)
        info["pwr"] = pwr_cost(folder)
        info["ipm"] = folder.endswith("_IPM")
        runs.append(info)
        cap[folder] = capacity(folder)
        disp[folder] = dispatch(folder, sand)
        print(f"{scen} {ts}: {folder} ({info['file_ts']} TS) → {info['cost']:,.0f} · PWR {info['pwr']:,.0f}")

    data = {"years": YEARS, "disp_years": DISPATCH_YEARS, "runs": runs, "cap": cap, "disp": disp,
            "cap_families": CAP_FAMILIES, "groups": list(DISPATCH_GROUPS)}
    html = (TEMPLATE.read_text()
            .replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
            .replace("/*__GENERATED__*/", generated_at()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html)
    print(f"Reporte: {args.out} ({len(html) / 1e3:.0f} kB)")


if __name__ == "__main__":
    _main()
