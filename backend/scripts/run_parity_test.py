"""Prueba de paridad: ejecuta dos veces la simulación del escenario prueba final y compara resultados.

Comprueba que dos corridas consecutivas con los mismos datos dan el mismo resultado (determinismo).
Salida 0 si todo da igual; 1 si hay diferencias por encima de la tolerancia.

Uso (en contenedor o local con BD):
  python scripts/run_parity_test.py
  python scripts/run_parity_test.py --tolerance 1e-6
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Importar después de path
from run_prueba_final import main as run_simulation  # noqa: E402
from app.simulation.benchmark import compare_with_tolerance  # noqa: E402

METRIC_KEYS = ("objective_value", "coverage_ratio", "total_demand", "total_dispatch", "total_unmet")
OUTPUT_FILENAME = "prueba_final_result.json"
REF_FILENAME = "prueba_final_referencia.json"

# Tablas a comparar: clave para identificar filas y campos numéricos a comparar
TABLE_KEYS = {
    "dispatch": (("parameter_value_id", "region_id", "year", "technology_name", "fuel_name"), ("dispatch", "cost")),
    "unmet_demand": (("region_id", "year"), ("unmet_demand",)),
    "new_capacity": (("region_id", "technology_id", "year"), ("new_capacity",)),
    "annual_emissions": (("region_id", "year"), ("annual_emissions",)),
}


def load_metrics(path: Path) -> dict[str, float]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: float(data.get(k) or 0.0) for k in METRIC_KEYS}


def _row_key(row: dict, key_names: tuple[str, ...]) -> tuple:
    return tuple(row.get(k) for k in key_names)


def compare_tables(ref_data: dict, actual_data: dict, tolerance: float) -> tuple[bool, list[str]]:
    """Compara las tablas (dispatch, unmet_demand, new_capacity, annual_emissions)."""
    errors: list[str] = []
    all_ok = True
    for table_name, (key_names, value_names) in TABLE_KEYS.items():
        ref_list = ref_data.get(table_name) or []
        actual_list = actual_data.get(table_name) or []
        ref_map = {_row_key(r, key_names): r for r in ref_list}
        actual_map = {_row_key(r, key_names): r for r in actual_list}
        all_keys = sorted(set(ref_map) | set(actual_map))
        if len(ref_map) != len(actual_map) or set(ref_map) != set(actual_map):
            errors.append(f"  {table_name}: distinto número de filas o claves (ref={len(ref_map)}, actual={len(actual_map)})")
            all_ok = False
            continue
        for k in all_keys:
            ref_row = ref_map[k]
            actual_row = actual_map[k]
            for field in value_names:
                ref_val = float(ref_row.get(field) or 0.0)
                act_val = float(actual_row.get(field) or 0.0)
                if ref_val == 0.0 and act_val == 0.0:
                    continue
                rel = abs(act_val - ref_val) / (abs(ref_val) or 1e-15)
                if rel > tolerance:
                    all_ok = False
                    errors.append(f"  {table_name} {k} {field}: ref={ref_val} actual={act_val} (rel={rel:.2e})")
    return all_ok, errors


def main() -> int:
    tolerance = 1e-9
    if "--tolerance" in sys.argv:
        i = sys.argv.index("--tolerance")
        if i + 1 < len(sys.argv):
            tolerance = float(sys.argv[i + 1])

    out_dir = PROJECT_ROOT / "tmp"
    out_dir.mkdir(parents=True, exist_ok=True)
    ref_path = out_dir / REF_FILENAME
    actual_path = out_dir / OUTPUT_FILENAME

    print("=== Prueba de paridad (Escenario prueba final) ===\n")
    print("1. Primera corrida (referencia)...")
    if run_simulation() != 0:
        return 1
    if not actual_path.exists():
        print("[ERROR] No se generó el resultado de la primera corrida.")
        return 1
    ref_path.write_text(actual_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"    Referencia guardada en {ref_path}\n")

    print("2. Segunda corrida (actual)...")
    if run_simulation() != 0:
        return 1
    if not actual_path.exists():
        print("[ERROR] No se generó el resultado de la segunda corrida.")
        return 1
    print(f"    Actual guardado en {actual_path}\n")

    print("3. Comparación de métricas agregadas...")
    ref_data = json.loads(ref_path.read_text(encoding="utf-8"))
    actual_data = json.loads(actual_path.read_text(encoding="utf-8"))
    ref_metrics = load_metrics(ref_path)
    actual_metrics = {k: float(actual_data.get(k) or 0.0) for k in METRIC_KEYS}
    is_ok, metric_errors = compare_with_tolerance(
        reference=ref_metrics,
        actual=actual_metrics,
        tolerance=tolerance,
    )

    print("   Métricas referencia:", ref_metrics)
    print("   Métricas actual    :", actual_metrics)
    print("   Errores relativos :", metric_errors)
    print("   Tolerancia        :", tolerance)

    print("\n4. Comparación de tablas (dispatch, unmet_demand, new_capacity, annual_emissions)...")
    tables_ok, table_errors = compare_tables(ref_data, actual_data, tolerance)
    if table_errors:
        for e in table_errors:
            print(e)
    else:
        print("   dispatch: OK (mismo número de filas y valores)")
        print("   unmet_demand: OK")
        print("   new_capacity: OK")
        print("   annual_emissions: OK")

    if is_ok and tables_ok:
        print("\n[OK] Todo da igual: métricas y tablas idénticas dentro de la tolerancia.")
        return 0
    print("\n[FAIL] Las dos corridas difieren (métricas y/o tablas).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
