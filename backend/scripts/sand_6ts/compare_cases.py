"""Compara corridas 2 TS vs 6 TS a partir de las salidas de run_osemosys_cli.py.

Lee ``tmp/sand/runs/<caso>/`` (resultados) y ``tmp/sand/runs/<caso>.log`` (tiempo).
Reporta costo total, capacidad y generación eléctrica por familia, y la
generación por timeslice de cada caso.

Uso (desde backend/):
  python scripts/sand_6ts/compare_cases.py 2TS 6TS_CAL 6TS_UPME
"""

from __future__ import annotations

import argparse
import re

import pandas as pd

from common import RUNS_DIR

YEARS = [2030, 2040, 2055]
PJ_PER_GW_YEAR = 31.536  # CapacityToActivityUnit = 1: capacidad en PJ/año

# Familias de generación eléctrica (prefijo → familia), en orden de prioridad.
FAMILIES = [
    ("PWRSOL", "Solar"), ("PWRCSP", "Solar"), ("PWRWND", "Eólica"),
    ("PWRHYD", "Hidro"), ("PWRNGS", "Gas"), ("PWRCOA", "Carbón"),
    ("PWRNUC", "Nuclear"), ("PWRGEO", "Geotermia"), ("PWRBGS", "Biomasa"),
    ("PWRAFR", "Biomasa"), ("PWR", "Otros"),
]


def family(tech: str) -> str | None:
    return next((f for p, f in FAMILIES if tech.startswith(p)), None)


def read_case(name: str) -> dict:
    d = RUNS_DIR / name
    summary = pd.read_csv(d / "summary.csv").set_index("metric")["value"]
    log = (RUNS_DIR / f"{name}.log").read_text(errors="ignore")
    real = re.findall(r"^real\s+([\d.]+)", log, flags=re.M)

    cap = pd.read_csv(d / "TotalCapacityAnnual.csv")
    cap["VALUE"] /= PJ_PER_GW_YEAR
    prod = pd.read_csv(d / "ProductionByTechnology.csv").rename(columns={"DUMMY": "TIMESLICE"})
    for df in (cap, prod):
        df["FAMILY"] = df["TECHNOLOGY"].map(family)
    return {
        "status": summary.get("solver_status"),
        "objective": float(summary.get("objective_value", "nan")),
        "seconds": float(real[-1]) if real else float("nan"),
        "cap": cap.dropna(subset=["FAMILY"]),
        "prod": prod.dropna(subset=["FAMILY"]),
    }


def by_family(cases: dict, key: str) -> pd.DataFrame:
    frames = []
    for name, c in cases.items():
        t = c[key][c[key]["YEAR"].isin(YEARS)].groupby(["FAMILY", "YEAR"])["VALUE"].sum()
        frames.append(t.rename(name))
    out = pd.concat(frames, axis=1).unstack("YEAR").fillna(0.0)
    out.columns = [f"{case}_{year}" for case, year in out.columns]
    return out[[f"{c}_{y}" for y in YEARS for c in cases]]


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cases", nargs="+")
    parser.add_argument("--year", type=int, default=2030, help="Año para la generación por TS.")
    args = parser.parse_args()

    cases = {n: read_case(n) for n in args.cases}
    base = args.cases[0]
    pd.set_option("display.width", 250)

    print("== Costo total descontado")
    rows = []
    for n, c in cases.items():
        delta = (c["objective"] / cases[base]["objective"] - 1) * 100
        rows.append({"caso": n, "estado": c["status"], "objetivo": round(c["objective"], 2),
                     f"Δ% vs {base}": round(delta, 3), "tiempo_s": c["seconds"]})
    print(pd.DataFrame(rows).to_string(index=False))

    print("\n== Capacidad eléctrica por familia (GW)")
    print(by_family(cases, "cap").round(2).to_string())
    print("\n== Generación eléctrica por familia (PJ)")
    print(by_family(cases, "prod").round(1).to_string())

    for n, c in cases.items():
        p = c["prod"][c["prod"]["YEAR"] == args.year]
        t = p.pivot_table(index="FAMILY", columns="TIMESLICE", values="VALUE", aggfunc="sum").fillna(0.0)
        print(f"\n== Generación por TS {args.year} (PJ) — {n}")
        print(t.round(2).to_string())


if __name__ == "__main__":
    _main()
