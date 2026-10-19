"""Compara una corrida UPME de Atlantis contra la referencia oficial (MPS + HiGHS).

Requiere haber generado la referencia con ``build_atlantis.py --solve-reference``
(deja ``out/atlantis/atlantis_<tag>.mps``) y corrido el CLI UPME con
``-o out/atlantis/upme_<tag_upme>``.

Uso (desde backend/):
  python scripts/atlantis_case/compare_atlantis.py --upme 2TS_NOSTO --ref 2TS_NOSTO_NORE
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import highspy
import pandas as pd

from build_atlantis import SOURCE_DATA, SOURCE_MODEL, read_case

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = REPO_ROOT / "out" / "atlantis"

# Variable -> posición, en el CSV UPME, de cada índice de la variable oficial.
# ProductionByTechnology sale como (r, t, f, l, y); el oficial es (r, l, t, f, y).
VARIABLES = {
    "TotalDiscountedCost": None,
    "TotalCapacityAnnual": None,
    "ProductionByTechnology": [0, 3, 1, 2, 4],
    "AnnualTechnologyEmission": None,
    "ModelPeriodEmissions": None,
}


def solve_reference(tag: str) -> tuple[float, dict[str, dict[tuple[str, ...], float]]]:
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    h.readModel(str(OUT_DIR / f"atlantis_{tag}.mps"))
    h.run()
    values: dict[str, dict[tuple[str, ...], float]] = {v: {} for v in VARIABLES}
    for name, val in zip(h.getLp().col_names_, h.getSolution().col_value):
        m = re.match(r"(\w+)\[(.*)\]$", name)
        if m and m.group(1) in values:
            values[m.group(1)][tuple(m.group(2).split(","))] = val
    _clean_reference_emissions(values)
    return h.getInfo().objective_function_value, values


def _clean_reference_emissions(values: dict) -> None:
    """En osemosys.txt, E1 solo existe donde EmissionActivityRatio != 0; el
    resto de variables de emisión queda libre (degenerado, hasta el límite
    99999). Se conservan solo las (t, e) con factor y se recalcula el total."""
    ear = read_case(SOURCE_DATA, SOURCE_MODEL).params["EmissionActivityRatio"].values
    emitting = {(t, e) for (_, t, e, _, _), v in ear.items() if v != 0}
    ate = {k: v for k, v in values["AnnualTechnologyEmission"].items() if (k[1], k[2]) in emitting}
    values["AnnualTechnologyEmission"] = ate
    total: dict[tuple[str, ...], float] = {}
    for (r, _, e, _), v in ate.items():
        total[(r, e)] = total.get((r, e), 0.0) + v
    values["ModelPeriodEmissions"] = total


def _annual_production(d: dict) -> dict:
    out: dict[tuple[str, ...], float] = {}
    for (r, _, t, f, y), v in d.items():
        out[(r, t, f, y)] = out.get((r, t, f, y), 0.0) + v
    return out


def read_upme(tag: str, var: str) -> dict[tuple[str, ...], float]:
    path = OUT_DIR / f"upme_{tag}" / f"{var}.csv"
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str)
    order = VARIABLES[var] or list(range(len(df.columns) - 1))
    return {tuple(row[i] for i in order): float(row[-1]) for row in df.itertuples(index=False)}


def compare(upme_tag: str, ref_tag: str, tol: float = 1e-6) -> int:
    ref_obj, ref = solve_reference(ref_tag)
    summary = pd.read_csv(OUT_DIR / f"upme_{upme_tag}" / "summary.csv")
    print(f"UPME {upme_tag} vs referencia {ref_tag}")
    print(summary.to_string(index=False))
    print(f"  objetivo referencia: {ref_obj:.6f}")

    upme = {var: read_upme(upme_tag, var) for var in VARIABLES}
    # El reparto por timeslice puede ser un óptimo alternativo; el anual no.
    upme["ProductionAnnual"] = _annual_production(upme["ProductionByTechnology"])
    ref["ProductionAnnual"] = _annual_production(ref["ProductionByTechnology"])

    n_bad = 0
    for var in upme:
        u = upme[var]
        r = ref[var]
        if not u:
            print(f"  {var:28s} sin CSV UPME")
            continue
        keys = set(u) | {k for k, v in r.items() if abs(v) > tol}
        diffs = sorted(
            ((k, u.get(k, 0.0), r.get(k, 0.0)) for k in keys
             if abs(u.get(k, 0.0) - r.get(k, 0.0)) > tol * max(1.0, abs(r.get(k, 0.0)))),
            key=lambda d: -abs(d[1] - d[2]),
        )
        n_bad += bool(diffs)
        print(f"  {var:28s} {len(keys):6d} claves, {len(diffs):5d} difieren")
        for k, uv, rv in diffs[:5]:
            print(f"      {','.join(k):55s} UPME={uv:14.6f} ref={rv:14.6f}")
    return n_bad


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--upme", required=True, help="Tag de la corrida UPME (p. ej. 2TS_NOSTO)")
    parser.add_argument("--ref", required=True, help="Tag de la referencia (p. ej. 2TS_NOSTO_NORE)")
    args = parser.parse_args()
    compare(args.upme, args.ref)


if __name__ == "__main__":
    _main()
