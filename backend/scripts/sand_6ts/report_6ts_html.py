"""Genera el reporte HTML que compara PD, PA y CN con 2 y 6 TS.

Lee las corridas de ``tmp/sand/runs/<carpeta>/`` y sus logs. El archivo SAND de
cada corrida se toma del log (la ruta que recibió ``run_osemosys_cli.py``), y
del propio .xlsx se calculan la huella SHA-256 y el número de timeslices, para
que el reporte muestre lo que realmente se resolvió.

Las gráficas de la app salen de ``ui_charts_from_runs.py`` (motor de la app):
  python scripts/sand_6ts/ui_charts_from_runs.py 2TS 6TS_v19oct PA_2TS PA_6TS CN_2TS CN_6TS \
      --out ../tmp/sand/runs/ui_charts_3esc.json

Uso (desde backend/):
  python scripts/sand_6ts/report_6ts_html.py
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from common import INPUTS_DIR, OUTPUTS_DIR, REPO_ROOT, RUNS_DIR

TEMPLATE = Path(__file__).with_name("report_6ts_template.html")
# Fuente a mano de Excalidraw para el diagrama (OFL 1.1, ver assets/README.md).
FONT = Path(__file__).with_name("assets") / "Excalifont-Regular-latin.woff2"

# (escenario, resolución, carpeta de la corrida)
CASES = [
    ("PD", "2TS", "2TS"), ("PD", "6TS", "6TS_v19oct"),
    ("PA", "2TS", "PA_2TS"), ("PA", "6TS", "PA_6TS"),
    ("CN", "2TS", "CN_2TS"), ("CN", "6TS", "CN_6TS"),
]
YEARS_KPI = [2030, 2040, 2055]
DISPATCH_YEAR = 2030
PJ_PER_GW_YEAR = 31.536
HOURS = 8760

FAMILIES = [  # prefijo → familia (orden de prioridad)
    ("PWRSOL", "Solar"), ("PWRCSP", "Solar"), ("PWRWND", "Eólica"), ("PWRHYD", "Hidro"),
    ("PWRNGS", "Gas"), ("PWRCOA", "Carbón"), ("PWRNUC", "Nuclear"), ("PWRGEO", "Geotermia"),
    ("PWR", "Otras"),
]
# Familias que se muestran en las gráficas de 2022–2055 y en el despacho.
PLOT_FAMILIES = ["Hidro", "Solar", "Eólica", "Gas", "Carbón", "Nuclear", "Geotermia", "Otras"]
CF_TECHS = {"PWRSOLUGE": "Solar (UGE)", "PWRWNDONS": "Eólica on-shore",
            "PWRWNDOFS_FIX": "Eólica off-shore", "PWRHYDDAM": "Hidro embalse"}
LINE_CHARTS = {"factor_planta", "elec_fp_liquidos", "elec_fp_termica"}


def family(tech: str) -> str | None:
    return next((f for p, f in FAMILIES if tech.startswith(p)), None)


def sand_of(folder: str) -> Path:
    log = (RUNS_DIR / f"{folder}.log").read_text(errors="ignore")
    m = re.search(r"([\w./-]+\.xlsx)", log)
    if not m:
        raise SystemExit(f"{folder}.log no dice qué archivo SAND usó.")
    path = (REPO_ROOT / "backend" / m.group(1)).resolve()
    if path.exists():
        return path
    # Logs anteriores a la mudanza a tmp/sand/ apuntan a ../SAND/…: se busca por nombre.
    found = [p for d in (INPUTS_DIR, OUTPUTS_DIR) for p in d.rglob(path.name)]
    if not found:
        raise SystemExit(f"No se encuentra {path.name} (log de {folder}) en {INPUTS_DIR.parent}.")
    return found[0]


def read_sand(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Parameters")
    df.columns = [str(c) for c in df.columns]
    return df


def run_info(scen: str, ts: str, folder: str) -> tuple[dict, pd.DataFrame]:
    log = (RUNS_DIR / f"{folder}.log").read_text(errors="ignore")
    summary = pd.read_csv(RUNS_DIR / folder / "summary.csv").set_index("metric")["value"]
    sand = sand_of(folder)
    df = read_sand(sand)
    solver_s = re.findall(r"HiGHS run time\s*:\s*([\d.]+)", log)
    prod = pd.read_csv(RUNS_DIR / folder / "ProductionByTechnology.csv")
    info = {
        "scen": scen, "ts": ts, "folder": folder,
        "file": sand.name, "path": str(sand.relative_to(REPO_ROOT)),
        "sha": hashlib.sha256(sand.read_bytes()).hexdigest()[:12],
        "file_ts": int(df.loc[df["Parameter"] == "YearSplit", "TIMESLICE"].nunique()),
        "rows": len(df),
        "status": str(summary.get("solver_status")),
        "cost": float(summary["objective_value"]),
        "solver_s": float(solver_s[-1]) if solver_s else None,
        "backstop": float(prod.loc[prod["TECHNOLOGY"].str.startswith("BACKSTOP"), "VALUE"].sum()),
    }
    return info, df


def family_series(folder: str, years: list[int]) -> dict:
    cap = pd.read_csv(RUNS_DIR / folder / "TotalCapacityAnnual.csv")
    cap["F"] = cap["TECHNOLOGY"].map(family)
    cap = cap.dropna(subset=["F"]).groupby(["F", "YEAR"])["VALUE"].sum() / PJ_PER_GW_YEAR
    prod = pd.read_csv(RUNS_DIR / folder / "ProductionByTechnology.csv").rename(columns={"DUMMY": "TS"})
    prod["F"] = prod["TECHNOLOGY"].map(family)
    prod = prod.dropna(subset=["F"])
    gen = prod.groupby(["F", "YEAR"])["VALUE"].sum()

    def table(s: pd.Series, nd: int) -> dict:
        u = s.unstack("YEAR").reindex(columns=years).fillna(0.0)
        return {f: [round(float(v), nd) for v in u.loc[f]] if f in u.index else [0.0] * len(years)
                for f in PLOT_FAMILIES}

    return {"cap": table(cap, 3), "gen": table(gen, 2), "prod": prod}


def dispatch(prod: pd.DataFrame, ys: pd.Series) -> dict:
    """Potencia media (GW) por familia y TS en DISPATCH_YEAR."""
    p = prod[prod["YEAR"] == DISPATCH_YEAR].groupby(["F", "TS"])["VALUE"].sum().unstack("TS").fillna(0.0)
    hours = ys * HOURS
    gw = p.div(hours * 3.6e-3, axis=1)  # PJ / (h · 0.0036 PJ/GWh)
    return {f: {ts: round(float(gw.loc[f, ts]), 3) for ts in gw.columns} for f in gw.index}


def year_split(df: pd.DataFrame) -> pd.Series:
    return df[df["Parameter"] == "YearSplit"].set_index("TIMESLICE")[str(DISPATCH_YEAR)].astype(float)


def inputs(sands: dict) -> dict:
    """Perfil de demanda y CF por bloque, y si son iguales en los tres escenarios."""
    y = str(DISPATCH_YEAR)
    out, same = {}, {}
    for key in ("ratio", "cf6", "cf2"):
        same[key] = True
    first = None
    for scen in ("PD", "PA", "CN"):
        d6, d2 = sands[(scen, "6TS")], sands[(scen, "2TS")]
        ys6 = year_split(d6)
        sdp = d6[d6["Parameter"] == "SpecifiedDemandProfile"]
        sad = d6[d6["Parameter"] == "SpecifiedAnnualDemand"]
        fuel = sad.loc[sad[y] > 0, "FUEL"].iloc[0]
        prof = sdp[sdp["FUEL"] == fuel].set_index("TIMESLICE")[y].astype(float)
        cf = lambda d: {name: d[(d["Parameter"] == "CapacityFactor") & (d["TECHNOLOGY"] == t)]
                        .set_index("TIMESLICE")[y].astype(float).round(4).to_dict()
                        for t, name in CF_TECHS.items()}
        cur = {"ratio": (prof / ys6).round(4).to_dict(), "cf6": cf(d6), "cf2": cf(d2)}
        # En los exports de la BD falta la fila de CF = 1: se completa con el default.
        for name, v in cur["cf2"].items():
            for ts in ("S101", "S102"):
                v.setdefault(ts, 1.0)
        if first is None:
            first = cur
        else:
            for key in same:
                same[key] &= json.dumps(cur[key], sort_keys=True) == json.dumps(first[key], sort_keys=True)
        sad_tot = float(sad[y].sum())
        out.setdefault("sad_pj", {})[scen] = round(sad_tot, 1)
    out.update(first)
    out["ys6"] = year_split(sands[("PD", "6TS")]).round(4).to_dict()
    out["same"] = same
    return out


def compact_ui(ui: dict, folders: list[str]) -> dict:
    charts = {}
    for tipo, c in ui["charts"].items():
        cases = {}
        for f in folders:
            r = c["cases"].get(f)
            if not r:
                cases[f] = None
                continue
            cases[f] = {"cats": r["categories"], "s": [
                [s["name"], s["color"], [None if v is None else round(float(v), 4) for v in s["data"]]]
                for s in r["series"]]}
        charts[tipo] = {"label": c["label"], "unit": c["unit"],
                        "kind": "line" if tipo in LINE_CHARTS else "bar", "cases": cases}
    modules = [{"label": m["label"], "charts": [[i["tipo"], i["subsector"]] for i in m["charts"]]}
               for m in ui["modules"]]
    return {"modules": modules, "charts": charts}


def gei_series(ui: dict, folder: str, years: list[int]) -> list[float]:
    r = ui["charts"]["emisiones_gei"]["cases"][folder]
    cats = [int(c) for c in r["categories"]]
    tot = [sum((s["data"][i] or 0) for s in r["series"]) for i in range(len(cats))]
    m = dict(zip(cats, tot))
    return [round(m.get(y, 0.0), 3) for y in years]


MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]


def generated_at() -> str:
    """Fecha y hora local de generación, p. ej. '19 de octubre de 2026, 19:52 EDT'."""
    now = datetime.now().astimezone()
    return f"{now.day} de {MONTHS[now.month - 1]} de {now.year}, {now:%H:%M} {now.tzname()}"


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ui", type=Path, default=RUNS_DIR / "ui_charts_3esc.json")
    parser.add_argument("--out", type=Path, default=RUNS_DIR / "report" / "dia-tipico-6ts.html")
    args = parser.parse_args()

    ui = json.loads(args.ui.read_text())
    folders = [f for _, _, f in CASES]
    missing = [f for f in folders if f not in ui["cases"]]
    if missing:
        raise SystemExit(f"{args.ui.name} no tiene las corridas {missing}; regenera ui_charts_from_runs.py.")

    runs, sands, fam, disp, gei = [], {}, {}, {}, {}
    years = None
    for scen, ts, folder in CASES:
        info, df = run_info(scen, ts, folder)
        runs.append(info)
        sands[(scen, ts)] = df
        if years is None:
            years = sorted(pd.read_csv(RUNS_DIR / folder / "TotalCapacityAnnual.csv")["YEAR"].unique().tolist())
        fs = family_series(folder, years)
        fam[folder] = {"cap": fs["cap"], "gen": fs["gen"]}
        disp[folder] = dispatch(fs["prod"], year_split(df))
        gei[folder] = gei_series(ui, folder, years)
        print(f"{scen} {ts}: {info['file']} ({info['file_ts']} TS, sha {info['sha']}) → {info['cost']:,.0f}")

    data = {
        "years": years, "kpi_years": YEARS_KPI, "dispatch_year": DISPATCH_YEAR,
        "runs": runs, "fam": fam, "disp": disp, "gei": gei, "families": PLOT_FAMILIES,
        "inputs": inputs(sands), "ui": compact_ui(ui, folders),
    }
    html = (TEMPLATE.read_text()
            .replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
            .replace("/*__GENERATED__*/", generated_at())
            .replace("/*__EXCALIFONT__*/", base64.b64encode(FONT.read_bytes()).decode()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html)
    print(f"Reporte: {args.out} ({len(html) / 1e6:.1f} MB)")


if __name__ == "__main__":
    _main()
