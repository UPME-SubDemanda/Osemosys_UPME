"""Analiza la punta eléctrica de corridas con distintos timeslices (2, 6 u 8 TS).

Para cada caso y año reporta, por TS, la generación eléctrica media en GW por
familia, la capacidad eléctrica instalada frente a la generación de punta y el
uso de la hidro de embalse frente a su tope del bloque (capacidad × CF).
Lee las corridas de ``tmp/sand/runs/<caso>/`` y el SAND de cada una desde su log.

Uso (desde backend/):
  python scripts/sand_8ts/peak_analysis.py 6TS_v19oct 8TS_PB3H130 --years 2030 2040 2055
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sand_6ts"))

from common import RUNS_DIR, read_sand  # noqa: E402
from compare_cases import PJ_PER_GW_YEAR, family  # noqa: E402
from report_6ts_html import sand_of  # noqa: E402

GW_PER_PJ_H = 1e15 / 3.6e12  # PJ en h → GW medios
HYDRO_DAM = "PWRHYDDAM"


def load(case: str) -> dict:
    d = RUNS_DIR / case
    sand = read_sand(sand_of(case))
    years = [c for c in sand.columns if c.isdigit()]
    hours = sand[sand["Parameter"] == "YearSplit"].set_index("TIMESLICE")[years].astype(float) * 8760
    cf = sand[sand["Parameter"] == "CapacityFactor"].set_index(["TECHNOLOGY", "TIMESLICE"])[years].astype(float)
    prod = pd.read_csv(d / "ProductionByTechnology.csv").rename(columns={"DUMMY": "TS"})
    prod["FAMILY"] = prod["TECHNOLOGY"].map(family)
    cap = pd.read_csv(d / "TotalCapacityAnnual.csv")
    cap["GW"] = cap["VALUE"] / PJ_PER_GW_YEAR
    cap["FAMILY"] = cap["TECHNOLOGY"].map(family)
    return {"hours": hours, "cf": cf, "prod": prod.dropna(subset=["FAMILY"]), "cap": cap}


def report(case: str, c: dict, year: int) -> None:
    y = str(year)
    hours = c["hours"][y]
    p = c["prod"][c["prod"]["YEAR"] == year]
    gw = p.pivot_table(index="FAMILY", columns="TS", values="VALUE", aggfunc="sum").fillna(0.0)
    gw = gw[hours.index] * GW_PER_PJ_H / hours
    gw.loc["TOTAL"] = gw.sum()

    cap = c["cap"][c["cap"]["YEAR"] == year]
    cap_elc = cap.dropna(subset=["FAMILY"])["GW"].sum()
    dam_cap = cap.loc[cap["TECHNOLOGY"] == HYDRO_DAM, "GW"].sum()
    dam_gen = p[p["TECHNOLOGY"] == HYDRO_DAM].groupby("TS")["VALUE"].sum().reindex(hours.index, fill_value=0.0)
    dam_gw = dam_gen * GW_PER_PJ_H / hours
    dam_max = dam_cap * c["cf"].loc[HYDRO_DAM][y].reindex(hours.index)

    print(f"\n== {case} — {year}: generación eléctrica media por TS (GW)")
    print(gw.round(2).to_string())
    peak_ts = gw.loc["TOTAL"].idxmax()
    print(f"Punta: {peak_ts} con {gw.loc['TOTAL', peak_ts]:.2f} GW · capacidad eléctrica instalada "
          f"{cap_elc:.2f} GW (margen {cap_elc / gw.loc['TOTAL', peak_ts] - 1:+.1%})")
    use = pd.DataFrame({"GW": dam_gw, "tope GW": dam_max, "uso": dam_gw / dam_max})
    print(f"Hidro embalse ({dam_cap:.2f} GW instalados):")
    print(use.T.round(3).to_string())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cases", nargs="+")
    parser.add_argument("--years", type=int, nargs="+", default=[2030, 2040, 2055])
    args = parser.parse_args()
    pd.set_option("display.width", 250)
    cases = {n: load(n) for n in args.cases}
    for year in args.years:
        for n, c in cases.items():
            report(n, c, year)


if __name__ == "__main__":
    main()
