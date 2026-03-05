"""Compara el resultado del último escenario (app) con una referencia del notebook.

Busca el resultado más reciente en tmp/ (sand_04_02_2026_result.json, app_result_*.json,
simulation-results/simulation_job_*.json) y, si existe referencia del notebook,
comprueba paridad. Si no hay referencia, imprime las métricas de la app para
comparar a mano con el notebook.

Uso:
  python scripts/compare_last_with_notebook.py
  python scripts/compare_last_with_notebook.py --ref tmp/referencia_notebook_sand.json
  python scripts/compare_last_with_notebook.py --tolerance 1e-3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.simulation.benchmark import compare_with_tolerance

METRIC_KEYS = ("objective_value", "coverage_ratio", "total_demand", "total_dispatch", "total_unmet")

# Orden de preferencia para "último resultado" de la app
CANDIDATE_ACTUAL = [
    PROJECT_ROOT / "tmp" / "sand_04_02_2026_result.json",
    PROJECT_ROOT / "tmp" / "app_result_job12.json",
]
CANDIDATE_REF = [
    PROJECT_ROOT / "tmp" / "referencia_notebook_sand.json",
    PROJECT_ROOT / "tmp" / "referencia_notebook.json",
]


def load_metrics(path: Path) -> dict[str, float]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: float(data.get(k) or 0.0) for k in METRIC_KEYS}


def find_latest_result() -> Path | None:
    """Devuelve la ruta al resultado más reciente (por mtime)."""
    found: list[tuple[float, Path]] = []
    for p in CANDIDATE_ACTUAL:
        if p.exists():
            found.append((p.stat().st_mtime, p))
    sim_dir = PROJECT_ROOT / "tmp" / "simulation-results"
    if sim_dir.exists():
        for f in sim_dir.glob("simulation_job_*.json"):
            found.append((f.stat().st_mtime, f))
    if not found:
        return None
    found.sort(key=lambda x: -x[0])
    return found[0][1]


def find_reference() -> Path | None:
    for p in CANDIDATE_REF:
        if p.exists():
            return p
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Comparar último resultado de la app con referencia del notebook")
    parser.add_argument("--ref", type=Path, help="JSON de referencia (notebook). Si no se pasa, se busca en tmp/")
    parser.add_argument("--actual", type=Path, help="JSON del resultado actual (app). Si no se pasa, se usa el más reciente en tmp/")
    parser.add_argument("--tolerance", type=float, default=1e-4, help="Tolerancia error relativo (default 1e-4)")
    args = parser.parse_args()

    actual_path = args.actual or find_latest_result()
    if not actual_path or not actual_path.exists():
        print("[ERROR] No se encontró ningún resultado de la app en tmp/ (sand_04_02_2026_result.json, app_result_*.json, simulation-results/simulation_job_*.json).")
        return 1

    ref_path = args.ref or find_reference()
    print(f"Resultado app (actual): {actual_path}")
    actual_metrics = load_metrics(actual_path)

    if ref_path is None:
        print("\nNo hay archivo de referencia del notebook en tmp/ (referencia_notebook_sand.json o referencia_notebook.json).")
        print("Métricas del último resultado (app) para comparar con el notebook:\n")
        for k in METRIC_KEYS:
            print(f"  {k}: {actual_metrics[k]}")
        print("\nPara comprobar paridad:")
        print("  1. En el notebook, tras resolver, exporta un JSON con esas claves (objective_value, total_demand, total_dispatch, total_unmet, coverage_ratio).")
        print("  2. Guárdalo como backend/tmp/referencia_notebook_sand.json")
        print("  3. Vuelve a ejecutar: python scripts/compare_last_with_notebook.py")
        return 0

    print(f"Referencia (notebook): {ref_path}")
    ref_metrics = load_metrics(ref_path)
    is_ok, errors = compare_with_tolerance(
        reference=ref_metrics,
        actual=actual_metrics,
        tolerance=args.tolerance,
    )
    print("\nMétricas de referencia (notebook):", ref_metrics)
    print("Métricas actuales (app)         :", actual_metrics)
    print("Errores relativos              :", errors)
    print("Tolerancia                     :", args.tolerance)
    if is_ok:
        print("\n[OK] Los resultados del último escenario coinciden con el notebook (dentro de la tolerancia).")
        return 0
    print("\n[FAIL] Hay diferencias por encima de la tolerancia.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
