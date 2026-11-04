"""Genera el reporte HTML de un escenario anidado (PD, PA o CN): 2 TS vs 6 TS anidado vs 8 TS anidado.

Solo compara casos con el mismo tratamiento del uso final: el 6 TS y el 8 TS
anidados escalan las mismas filas (capacidad × f, CapitalCost/FixedCost ÷ f,
TotalAnnualMinCapacityInvestment sin escalar), cada uno con su propio f. El
generador lo verifica contra el SAND del 2 TS y se detiene si no se cumple.
El 8 TS principal usa la punta medida en XM (×1,16 = 1,166 × promedio de la noche).
En el PD, el de punta ×1,30 queda como referencia y se incluye la prueba con formas
planas (8 TS anidado FLAT), que debe dar el 2 TS.

Uso (desde backend/):
  python scripts/sand_8ts/report_8ts_nest_html.py                 # PD
  python scripts/sand_8ts/report_8ts_nest_html.py --scenario PA
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sand_6ts"))

from common import CAPACITY_SENTINEL, PEAK_CAPACITY_PARAMS, PEAK_COST_PARAMS, RUNS_DIR, year_columns  # noqa: E402
from nest import tech_peak_factors  # noqa: E402
from report_6ts_html import family, generated_at, run_info  # noqa: E402
from report_8ts_html import CAP_FAMILIES, DISPATCH_GROUPS, DISPATCH_YEARS, YEARS, capacity, dispatch, pwr_cost  # noqa: E402

TEMPLATE = Path(__file__).resolve().parents[3] / "tmp" / "sand" / "templates" / "anidado_2_6_8ts.html"

# Por escenario: (clave, etiqueta, carpeta de la corrida). 6TS_NEST_R enlaza a 6TS_NEST/run_20261021_141628.
CASES = {
    "PD": [
        ("2TS", "2 TS", "2TS"),
        ("6TS", "6 TS anidado", "6TS_NEST_R"),
        ("8TS", "8 TS anidado, punta XM ×1,16", "8TS_NEST_PB3H116"),
        ("8TS130", "8 TS anidado, punta ×1,30", "8TS_NEST_PB3H130"),
        ("FLAT", "8 TS anidado, formas planas", "8TS_NEST_FLAT"),
    ],
    "PA": [
        ("2TS", "2 TS", "PA_2TS"),
        ("6TS", "6 TS anidado", "PA_6TS_NEST_02Nov2026"),
        ("8TS", "8 TS anidado, punta XM ×1,16", "PA_8TS_NEST_PB3H116_02Nov2026"),
    ],
    "CN": [
        ("2TS", "2 TS", "CN_2TS"),
        ("6TS", "6 TS anidado", "CN_6TS_NEST_02Nov2026"),
        ("8TS", "8 TS anidado, punta XM ×1,16", "CN_8TS_NEST_PB3H116_02Nov2026"),
    ],
}
LEAD_EXTRA = {"PD": " La corrida con la punta supuesta de ×1,30 queda como referencia."}
FINDINGS = {
    "PD": [
        '<b>La prueba con formas planas da exactamente el 2 TS.</b> Tanto en el costo total como en el costo eléctrico. El anidamiento no altera el modelo, así que cualquier diferencia viene del perfil.',
        '<b>Con la punta de XM, el 8 TS casi repite el 6 TS.</b> El costo total queda +0,002 % sobre el 6 TS y el costo eléctrico +1,3 % (29 472 frente a 29 098). La capacidad de 2055 es casi la misma: 2,96 GW de gas en los tres casos y 17,7 GW de eólica frente a 17,5.',
        '<b>El +10 % del costo eléctrico venía de la punta supuesta.</b> Con ×1,30 el modelo instalaba 0,72 GW más de gas en 2055 para cubrir la punta. Con ×1,16, el gas que genera en la punta (0,8–1,1 GW) cabe en la capacidad que ya existe.',
        '<b>El salto grande está entre 2 y 6 TS, no entre 6 y 8.</b> La eólica de 2055 baja de 19,8 a 17,5 GW al pasar de 2 a 6 TS y casi no se mueve con el bloque de punta. La solar queda igual en todos los casos, con toda su energía en el día.',
        '<b>En 2055 el bloque más exigido es el día, no la punta.</b> 20,0 GW en el día del semestre 1 frente a 17,5 GW en la punta. Partir más la noche aporta poco; lo que la medición de XM sugiere es partir el día.',
    ],
    "PA": [
        "<b>El 8 TS casi repite el 6 TS.</b> El costo total queda +0,005 % sobre el 6 TS y el costo eléctrico +1,4 % (32 709 frente a 32 249). Entre 2 y 6 TS el costo eléctrico prácticamente no cambia.",
        "<b>No hace falta capacidad firme nueva.</b> El gas queda en 2,96 GW en los tres casos. Lo que cambia es cuánto genera: en 2055 baja de 17,7 PJ con 2 TS a 9,1 PJ con 6 TS y 7,5 PJ con 8 TS, concentrado en la noche del segundo semestre.",
        "<b>La eólica sube un poco y la hidro genera menos.</b> En 2055 la eólica pasa de 22,4 GW con 2 TS a 23,2–23,3 GW con 6 y 8 TS. La hidro genera 210 PJ con 6 y 8 TS, frente a 232 PJ con 2 TS.",
        "<b>En 2055 el bloque más exigido sigue siendo el día, aunque por poco.</b> 22,0 GW en el día del semestre 1 frente a 21,0 GW en la punta.",
        "<b>El simplex dual resolvió el 8 TS anidado sin problemas</b> (44,7 min). El 8 TS viejo sin anidar de PA fallaba siempre con simplex dual.",
    ],
    "CN": [
        "<b>El 8 TS repite el 6 TS.</b> El costo total queda −0,03 % frente al 6 TS y el costo eléctrico +0,1 % (45 364 frente a 45 305). El paso de 2 a 6 TS baja el costo total 0,21 % y el eléctrico 0,8 %.",
        "<b>No hace falta capacidad firme nueva.</b> El gas queda en 3,75 GW en los tres casos y en 2040–2055 no genera. Solo opera en 2026–2030, de noche y por debajo de 1 GW.",
        "<b>La solar es la que más se mueve.</b> En 2055 pasa de 22,5 GW con 2 TS a 22,9 GW con 6 TS y 23,9 GW con 8 TS. La eólica queda en 51–52 GW en los tres casos.",
        "<b>La punta no es el bloque que define el sistema.</b> En 2055 el día del semestre 1 exige 48,8 GW, frente a 35,4 GW en la punta, y la punta genera lo mismo que el resto de la noche. El día tiene todo el peso de la solar y del hidrógeno.",
    ],
}
GEN_FAMILIES = ["Hidro", "Solar", "Eólica", "Gas", "Carbón", "Otras"]
TS_PARAMS = {"YearSplit", "SpecifiedDemandProfile", "CapacityFactor"}


def _key(df: pd.DataFrame, years: list[str]) -> pd.Index:
    cols = [c for c in df.columns if c not in years]
    return pd.Index(["|".join(map(str, r)) for r in df[cols].itertuples(index=False)])


def scaling(base: pd.DataFrame, sand: pd.DataFrame) -> dict:
    """Filas que difieren del 2 TS (fuera de los parámetros por TS) y su razón frente a f."""
    years = year_columns(base)
    b = base[years].astype(float).set_axis(_key(base, years))
    x = sand[years].astype(float).set_axis(_key(sand, years))
    tp = tech_peak_factors(base, {p: sand[sand["Parameter"] == p] for p in ("YearSplit", "SpecifiedDemandProfile")}, years)
    common = x.index.intersection(b.index)
    diff = [i for i in common[((x.loc[common] - b.loc[common]).abs() > 1e-9).any(axis=1)]
            if i.split("|")[0] not in TS_PARAMS]
    rows, bad = [], []
    for i in diff:
        param, tech = i.split("|")[0], i.split("|")[2]
        f = tp.loc[tech]
        expected = f if param in PEAK_CAPACITY_PARAMS else 1 / f
        # Valores "sin límite" y casi cero no se escalan (ver scale_peak_capacity).
        m = (b.loc[i].abs() > 1e-12) & (b.loc[i] < CAPACITY_SENTINEL)
        ok = np.allclose((x.loc[i] / b.loc[i])[m], expected[m], rtol=1e-9)
        (rows if ok else bad).append(i)
    if bad:
        raise SystemExit(f"Filas escaladas con razón distinta de f o 1/f: {bad[:5]}")
    by_param = pd.Series([i.split("|")[0] for i in diff]).value_counts()
    f_max = tp.max(axis=1)
    return {
        "rows": set(diff),
        "by_param": {p: int(by_param.get(p, 0)) for p in PEAK_CAPACITY_PARAMS + PEAK_COST_PARAMS
                     + ["TotalAnnualMinCapacityInvestment"]},
        "techs": int((f_max > 1 + 1e-9).sum()),
        "f": round(float(f_max.max()), 4),
    }


def blocks(sand: pd.DataFrame) -> dict:
    """Horas/año y demanda/promedio por TS en 2030 (perfil del primer fuel)."""
    ys = sand[sand["Parameter"] == "YearSplit"].set_index("TIMESLICE")["2030"].astype(float)
    sdp = sand[sand["Parameter"] == "SpecifiedDemandProfile"]
    sdp = sdp[sdp["FUEL"] == sdp["FUEL"].iloc[0]].set_index("TIMESLICE")["2030"].astype(float)
    return {ts: {"h": round(float(ys[ts] * 8760)), "r": round(float(sdp[ts] / ys[ts]), 3)} for ts in ys.index}


def generation(folder: str) -> dict:
    """Generación eléctrica anual (PJ) por familia en YEARS."""
    prod = pd.read_csv(RUNS_DIR / folder / "ProductionByTechnology.csv")
    prod["F"] = prod["TECHNOLOGY"].map(family).replace({"Nuclear": "Otras", "Geotermia": "Otras"})
    g = prod.dropna(subset=["F"]).groupby(["F", "YEAR"])["VALUE"].sum().unstack("YEAR")
    g = g.reindex(index=GEN_FAMILIES, columns=YEARS).fillna(0.0)
    return {f: [round(float(v), 1) for v in g.loc[f]] for f in GEN_FAMILIES}


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scenario", choices=list(CASES), default="PD")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    scen = args.scenario
    out = args.out or RUNS_DIR / "report" / f"{scen.lower()}-anidado-2-6-8ts.html"
    cases = CASES[scen]

    runs, cap, disp, gen, blk, scal = [], {}, {}, {}, {}, {}
    sands = {}
    for key, label, folder in cases:
        info, sand = run_info(scen, key, folder)
        info.update(key=key, label=label, pwr=pwr_cost(folder))
        runs.append(info)
        sands[key] = sand
        cap[key] = capacity(folder)
        disp[key] = dispatch(folder, sand)
        gen[key] = generation(folder)
        blk[key] = blocks(sand)
        print(f"{label}: {folder} ({info['file_ts']} TS) → {info['cost']:,.0f} · PWR {info['pwr']:,.0f}")

    for key in [k for k, _, _ in cases if k != "2TS"]:
        s = scaling(sands["2TS"], sands[key])
        scal[key] = s
        print(f"{key}: {len(s['rows'])} filas escaladas, f = {s['f']}, {s['techs']} tecnologías")
    for key in [k for k in ("8TS", "8TS130") if k in scal]:
        if scal["6TS"]["rows"] != scal[key]["rows"]:
            raise SystemExit(f"6 TS y {key} anidados no escalan las mismas filas: no son comparables.")
    if any(scal[k]["by_param"]["TotalAnnualMinCapacityInvestment"] for k in scal):
        raise SystemExit("TotalAnnualMinCapacityInvestment escalado: no debe escalarse.")
    for s in scal.values():
        s["rows"] = len(s["rows"])

    data = {"years": YEARS, "disp_years": DISPATCH_YEARS, "runs": runs, "cap": cap, "disp": disp, "gen": gen,
            "blocks": blk, "scaling": scal, "cap_families": CAP_FAMILIES, "gen_families": GEN_FAMILIES,
            "groups": list(DISPATCH_GROUPS)}
    findings = "\n      ".join(f"<li>{f}</li>" for f in FINDINGS.get(scen, []))
    html = (TEMPLATE.read_text()
            .replace("{{SCEN}}", scen).replace("{{LEAD_EXTRA}}", LEAD_EXTRA.get(scen, ""))
            .replace("{{FINDINGS}}", findings)
            .replace("{{RUNS_NOTE}}", " La fila de formas planas es la prueba del anidamiento." if "FLAT" in scal else "")
            .replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
            .replace("/*__GENERATED__*/", generated_at()))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"Reporte: {out} ({len(html) / 1e3:.0f} kB)")


if __name__ == "__main__":
    _main()
