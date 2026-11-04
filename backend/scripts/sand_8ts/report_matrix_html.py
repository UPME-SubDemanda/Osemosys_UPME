"""Genera los reportes HTML de la matriz eléctrica año a año (2022–2055) en PD, PA y CN.

Muestra la capacidad instalada (TotalCapacityAnnual), la capacidad nueva acumulada
(AccumulatedNewCapacity) y la generación por familia en cada año. Hay tres juegos de casos
(``--set``); todos escalan las mismas filas del uso final frente al 2 TS:

- ``todos``: 2 TS, 6 TS sin anidar (20 de octubre), 6 TS y 8 TS anidados (punta de XM, ×1,16),
  con y sin eólica UPME, y en el PD el 8 TS anidado ×1,30 como referencia. Incluye la sección
  "Impacto de anidar" (6 TS sin anidar contra 6 TS anidado).
- ``anidado``: solo 2 TS y los anidados de 6 y 8 TS (×1,16), con y sin eólica UPME.
- ``sin-anidar``: 2 TS, 6 TS sin anidar y 8 TS sin anidar ×1,16 (corrido el 3 de noviembre).

Los casos "eólica UPME" son anidados salvo la eólica, cuya energía anual del 2 TS se reparte con la
forma de la UPME (``--free-shape PWRWND``); en CN también se incluye eólica + hidro (solo en ``todos``).
El 6 TS sin anidar de CN se corrió el 2 de noviembre (la corrida del 20 de octubre no había terminado).

Uso (desde backend/):
  python scripts/sand_8ts/report_matrix_html.py [--set todos|anidado|sin-anidar]
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
from report_8ts_html import CAP_FAMILIES, pwr_cost  # noqa: E402

TEMPLATE = Path(__file__).resolve().parents[3] / "tmp" / "sand" / "templates" / "matriz_capacidad.html"

# Por escenario: (clave, etiqueta, carpeta de la corrida). La clave fija el estilo de línea en la plantilla.
CASES = {
    "PD": [
        ("2TS", "2 TS", "2TS"),
        ("6TS_SN", "6 TS sin anidar", "6TS_v20oct"),
        ("6TS", "6 TS anidado", "6TS_NEST_R"),
        ("6TS_EOL", "6 TS anidado, eólica UPME", "PD_6TS_NEST_EOLUPME_02Nov2026"),
        ("8TS", "8 TS anidado ×1,16", "8TS_NEST_PB3H116"),
        ("8TS_EOL", "8 TS anidado ×1,16, eólica UPME", "PD_8TS_NEST_PB3H116_EOLUPME_02Nov2026"),
        ("8TS130", "8 TS anidado ×1,30", "8TS_NEST_PB3H130"),
        ("8TS_SN", "8 TS sin anidar ×1,16", "PD_8TS_PB3H116_03Nov2026"),
    ],
    "PA": [
        ("2TS", "2 TS", "PA_2TS"),
        ("6TS_SN", "6 TS sin anidar", "PA_6TS_v20oct"),
        ("6TS", "6 TS anidado", "PA_6TS_NEST_02Nov2026"),
        ("6TS_EOL", "6 TS anidado, eólica UPME", "PA_6TS_NEST_EOLUPME_02Nov2026"),
        ("8TS", "8 TS anidado ×1,16", "PA_8TS_NEST_PB3H116_02Nov2026"),
        ("8TS_EOL", "8 TS anidado ×1,16, eólica UPME", "PA_8TS_NEST_PB3H116_EOLUPME_02Nov2026"),
        ("8TS_SN", "8 TS sin anidar ×1,16", "PA_8TS_PB3H116_03Nov2026"),
    ],
    "CN": [
        ("2TS", "2 TS", "CN_2TS"),
        ("6TS_SN", "6 TS sin anidar", "CN_6TS_v20oct_02Nov2026"),
        ("6TS", "6 TS anidado", "CN_6TS_NEST_02Nov2026"),
        ("6TS_EOL", "6 TS anidado, eólica UPME", "CN_6TS_NEST_EOLUPME_02Nov2026"),
        ("6TS_EOLHID", "6 TS anidado, eólica + hidro UPME", "CN_6TS_NEST_EOLHIDUPME_02Nov2026"),
        ("8TS", "8 TS anidado ×1,16", "CN_8TS_NEST_PB3H116_02Nov2026"),
        ("8TS_EOL", "8 TS anidado ×1,16, eólica UPME", "CN_8TS_NEST_PB3H116_EOLUPME_02Nov2026"),
        ("8TS_SN", "8 TS sin anidar ×1,16", "CN_8TS_PB3H116_03Nov2026"),
    ],
}

SCALING = ("Todos escalan las mismas filas del uso final frente al 2 TS (capacidad × f, CapitalCost y FixedCost ÷ f, "
           "<code>TotalAnnualMinCapacityInvestment</code> sin escalar), cada uno con su propio factor de punta f.")
EOL_NOTE = ("En los casos <b>eólica UPME</b> todo sigue anidado salvo la eólica, que reparte su energía anual del 2 TS "
            "con la forma de la UPME (nocturna) en vez de la del 2 TS (plana día/noche); van en trazo discontinuo largo.")

SN_EQUIV = ("Frente al reporte anidado no faltan los casos <b>eólica UPME</b>: el sin anidar ya usa la forma de la UPME para "
            "todas las tecnologías, eólica incluida, así que el 6 TS sin anidar equivale a la vez al 6 TS anidado y al anidado "
            "con eólica UPME (lo mismo en 8 TS). Los dos reportes tienen así los mismos niveles: 2, 6 y 8 TS con la punta ×1,16.")

# Por juego: claves de CASES que entran, textos de la plantilla y archivo de salida.
SETS = {
    "todos": {
        "keys": ("2TS", "6TS_SN", "6TS", "6TS_EOL", "6TS_EOLHID", "8TS", "8TS_EOL", "8TS130"),
        "title": "Matriz eléctrica por timeslices",
        "h1": "Matriz eléctrica con 2, 6 y 8 timeslices",
        "lead": "Capacidad eléctrica por familia en cada año de 2022 a 2055, en todos los casos comparables de cada escenario. " + SCALING,
        "notes": {},
        "nest": True,
        "sources_note": "No entran el 6 TS del 19 de octubre (escala 5 filas de <code>TotalAnnualMinCapacityInvestment</code>) "
                        "ni las versiones SINDIV (no dividen CapitalCost ni FixedCost).",
        "out": "matriz-capacidad-2-6-8ts.html",
    },
    "anidado": {
        "keys": ("2TS", "6TS", "6TS_EOL", "8TS", "8TS_EOL"),
        "title": "Matriz anidada 2-6-8 TS",
        "h1": "Matriz eléctrica con 2, 6 y 8 timeslices anidados",
        "lead": "Capacidad eléctrica por familia en cada año de 2022 a 2055, solo con los casos anidados: cada bloque del 6 y del 8 TS "
                "cae dentro de un bloque del 2 TS y conserva sus horas, su demanda y la energía de cada tecnología. El 6 TS parte cada "
                "semestre en madrugada (00–06), día (06–18) y noche (18–24); el 8 TS además parte la noche en punta (18–21, ×1,16 según XM) "
                "y resto (21–24). " + EOL_NOTE + " " + SCALING,
        "notes": {},
        "nest": False,
        "sources_note": "Solo casos anidados con la punta calibrada con XM (×1,16); no entra el 8 TS anidado ×1,30.",
        "out": "matriz-anidada-2-6-8ts.html",
    },
    "sin-anidar": {
        "keys": ("2TS", "6TS_SN", "8TS_SN"),
        "title": "Matriz sin anidar 2-6-8 TS",
        "h1": "Matriz eléctrica con 2, 6 y 8 timeslices sin anidar",
        "lead": "Capacidad eléctrica por familia en cada año de 2022 a 2055, con los casos sin anidar. El 6 TS usa los bloques de la UPME: "
                "madrugada, día de 11 h (06–17) y tarde-noche de 7 h (17–24), con los CF recalibrados a la energía anual (f = 1,077). "
                "El 8 TS sin anidar parte la tarde-noche en punta (3 h, ×1,16 según XM) y resto, igual que el anidado. " + SCALING + " " + SN_EQUIV,
        "notes": {},
        "nest": False,
        "sources_note": "Los 8 TS sin anidar ×1,16 se corrieron el 3 de noviembre. No entra el 8 TS sin anidar ×1,30 del "
                        "20 de octubre (otra punta; el del PD además escala <code>TotalAnnualMinCapacityInvestment</code>). No entran el 6 TS del 19 de octubre (escala 5 filas de <code>TotalAnnualMinCapacityInvestment</code>) "
                        "ni las versiones SINDIV (no dividen CapitalCost ni FixedCost).",
        "out": "matriz-sin-anidar-2-6-8ts.html",
    },
}


def by_year(folder: str, csv: str, years: list[int]) -> dict:
    """GW por familia en cada año a partir de una salida de capacidad (PJ/año)."""
    cap = pd.read_csv(RUNS_DIR / folder / csv)
    cap["F"] = cap["TECHNOLOGY"].map(family)
    gw = cap.dropna(subset=["F"]).groupby(["F", "YEAR"])["VALUE"].sum().div(PJ_PER_GW_YEAR)
    gw = gw.unstack("YEAR").reindex(index=CAP_FAMILIES, columns=years).fillna(0.0)
    return {f: [round(float(v), 3) for v in gw.loc[f]] for f in CAP_FAMILIES}


def generation(folder: str, years: list[int]) -> dict:
    """Generación eléctrica (PJ) por familia en cada año."""
    prod = pd.read_csv(RUNS_DIR / folder / "ProductionByTechnology.csv")
    prod["F"] = prod["TECHNOLOGY"].map(family)
    pj = prod.dropna(subset=["F"]).groupby(["F", "YEAR"])["VALUE"].sum()
    pj = pj.unstack("YEAR").reindex(index=CAP_FAMILIES, columns=years).fillna(0.0)
    return {f: [round(float(v), 2) for v in pj.loc[f]] for f in CAP_FAMILIES}


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--set", choices=SETS, default="todos")
    parser.add_argument("--out", type=Path, help="por omisión, tmp/sand/runs/report/<archivo del juego>")
    args = parser.parse_args()
    cfg = SETS[args.set]
    out_path = args.out or RUNS_DIR / "report" / cfg["out"]

    years = sorted(pd.read_csv(RUNS_DIR / "2TS" / "TotalCapacityAnnual.csv")["YEAR"].unique().tolist())
    scen = {}
    for name, cases in CASES.items():
        out = []
        for key, label, folder in [c for c in cases if c[0] in cfg["keys"]]:
            info, _ = run_info(name, key, folder)
            if info["status"] != "optimal":
                raise SystemExit(f"{folder}: la corrida no es óptima ({info['status']}).")
            out.append({"key": key, "label": label, "folder": folder, "file": info["file"], "cost": info["cost"],
                        "pwr": pwr_cost(folder),
                        "cap": by_year(folder, "TotalCapacityAnnual.csv", years),
                        "acc": by_year(folder, "AccumulatedNewCapacity.csv", years),
                        "gen": generation(folder, years)})
            print(f"{name} {label}: {folder} → {info['cost']:,.0f}")
        scen[name] = out

    data = {"set": args.set, "years": [int(y) for y in years], "families": CAP_FAMILIES, "scen": scen,
            "notes": cfg["notes"], "nest": cfg["nest"]}
    html = TEMPLATE.read_text()
    for k in ("title", "h1", "lead", "sources_note"):
        html = html.replace("{{%s}}" % k.upper(), cfg[k])
    html = (html
            .replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
            .replace("/*__GENERATED__*/", generated_at()))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
    print(f"Reporte: {out_path} ({len(html) / 1e3:.0f} kB)")


if __name__ == "__main__":
    _main()
