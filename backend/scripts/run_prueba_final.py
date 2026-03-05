"""Ejecuta la simulación OSeMOSYS para el escenario 'prueba final' y guarda el resultado.

Uso (desde raíz del backend, con venv activo):
  python scripts/run_prueba_final.py

Requisitos:
  - Escenario con nombre "prueba final" (o el indicado en PRUEBA_FINAL_SCENARIO_NAME) en la BD.
  - Catálogos y datos del escenario cargados.

Salida:
  - Imprime resumen en consola (objective_value, total_demand, total_dispatch, total_unmet, coverage_ratio).
  - Escribe JSON completo en backend/tmp/prueba_final_result.json para comparación con el notebook.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import SessionLocal
from app.models import Scenario
from app.simulation.osemosys_core import run_osemosys_from_db

PRUEBA_FINAL_SCENARIO_NAME = "Escenario prueba final"
OUTPUT_FILENAME = "prueba_final_result.json"


def main() -> int:
    """Ejecuta simulación para escenario 'prueba final' y persiste resultado."""
    with SessionLocal() as session:
        scenario = session.execute(
            select(Scenario).where(
                Scenario.name == PRUEBA_FINAL_SCENARIO_NAME,
                Scenario.is_template.is_(False),
            )
        ).scalar_one_or_none()

        if not scenario:
            print(f"[ERROR] No existe escenario con nombre '{PRUEBA_FINAL_SCENARIO_NAME}'.")
            print("        Crea el escenario en la app o ajusta PRUEBA_FINAL_SCENARIO_NAME en el script.")
            return 1

        print(f"Ejecutando simulación para escenario: {scenario.name} (id={scenario.id})")
        result = run_osemosys_from_db(
            session,
            scenario_id=scenario.id,
            solver_name="highs",
        )

    obj = float(result.get("objective_value", 0.0))
    total_demand = float(result.get("total_demand", 0.0))
    total_dispatch = float(result.get("total_dispatch", 0.0))
    total_unmet = float(result.get("total_unmet", 0.0))
    coverage = float(result.get("coverage_ratio", 0.0))
    status = result.get("solver_status", "?")

    print("\n--- Resumen (comparar con notebook) ---")
    print(f"  objective_value  : {obj}")
    print(f"  total_demand     : {total_demand}")
    print(f"  total_dispatch   : {total_dispatch}")
    print(f"  total_unmet      : {total_unmet}")
    print(f"  coverage_ratio   : {coverage}")
    print(f"  solver_status   : {status}")
    print("--------------------------------------\n")

    out_dir = PROJECT_ROOT / "tmp"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / OUTPUT_FILENAME
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Resultado completo guardado en: {out_path}")
    print("\nPara comparar con el notebook:")
    print("  1. En el notebook, anota objective_value y totales (o exporta a JSON).")
    print("  2. Ejecuta: python scripts/compare_results.py --ref referencia_notebook.json --actual tmp/prueba_final_result.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
