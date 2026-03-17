"""Compara resultados de simulación (notebook vs app) con tolerancia numérica.

Soporta dos modos:
  1) Comparación simple: --ref y --actual.
  2) Comparación múltiple: --pairs archivo_json con lista de pares.

Cada JSON puede contener solo métricas agregadas o el resultado completo de la app.
Si existen tablas (`dispatch`, `new_capacity`, `unmet_demand`, `annual_emissions`),
también se comparan fila a fila por clave.
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
TABLE_KEYS = {
    "dispatch": (("parameter_value_id", "region_id", "year", "technology_name", "fuel_name"), ("dispatch", "cost")),
    "unmet_demand": (("region_id", "year"), ("unmet_demand",)),
    "new_capacity": (("region_id", "technology_id", "year"), ("new_capacity",)),
    "annual_emissions": (("region_id", "year"), ("annual_emissions",)),
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_metrics(path: Path) -> dict[str, float]:
    """Carga un JSON y extrae métricas comparables."""
    data = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for k in METRIC_KEYS:
        if k in data and data[k] is not None:
            out[k] = float(data[k])
        else:
            out[k] = 0.0
    return out


def _row_key(row: dict, key_names: tuple[str, ...]) -> tuple:
    return tuple(row.get(k) for k in key_names)


def compare_tables(reference: dict, actual: dict, tolerance: float) -> tuple[bool, list[str]]:
    errors: list[str] = []
    ok = True
    for table_name, (key_names, value_names) in TABLE_KEYS.items():
        ref_rows = reference.get(table_name) or []
        act_rows = actual.get(table_name) or []
        if not ref_rows and not act_rows:
            continue
        ref_map = {_row_key(r, key_names): r for r in ref_rows}
        act_map = {_row_key(r, key_names): r for r in act_rows}
        if set(ref_map) != set(act_map):
            ok = False
            errors.append(
                f"{table_name}: claves distintas (ref={len(ref_map)}, actual={len(act_map)})"
            )
            continue
        for k in ref_map:
            rr = ref_map[k]
            ar = act_map[k]
            for field in value_names:
                rv = float(rr.get(field) or 0.0)
                av = float(ar.get(field) or 0.0)
                if rv == 0 and av == 0:
                    continue
                rel = abs(av - rv) / (abs(rv) or 1e-15)
                if rel > tolerance:
                    ok = False
                    errors.append(
                        f"{table_name} {k} {field}: ref={rv} actual={av} rel={rel:.3e}"
                    )
    return ok, errors


def _run_pair(ref_path: Path, actual_path: Path, tolerance: float) -> int:
    if not ref_path.exists():
        print(f"[ERROR] No existe archivo de referencia: {ref_path}")
        return 1
    if not actual_path.exists():
        print(f"[ERROR] No existe archivo actual: {actual_path}")
        return 1

    ref_metrics = load_metrics(ref_path)
    actual_metrics = load_metrics(actual_path)
    metrics_ok, metric_errors = compare_with_tolerance(
        reference=ref_metrics,
        actual=actual_metrics,
        tolerance=tolerance,
    )

    ref_json = _load_json(ref_path)
    actual_json = _load_json(actual_path)
    tables_ok, table_errors = compare_tables(ref_json, actual_json, tolerance)

    print(f"\n== Comparación ==")
    print(f"ref:    {ref_path}")
    print(f"actual: {actual_path}")
    print("Métricas ref   :", ref_metrics)
    print("Métricas actual:", actual_metrics)
    print("Errores métricas:", metric_errors)
    if table_errors:
        print("Errores tablas:")
        for err in table_errors[:50]:
            print(" -", err)
        if len(table_errors) > 50:
            print(f" - ... y {len(table_errors) - 50} errores más")
    else:
        print("Tablas: OK")

    if metrics_ok and tables_ok:
        print("[OK] Paridad dentro de tolerancia.")
        return 0
    print("[FAIL] Diferencias por encima de tolerancia.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Compara resultados de simulación (notebook vs app)")
    parser.add_argument("--ref", type=Path, help="JSON de referencia")
    parser.add_argument("--actual", type=Path, help="JSON actual")
    parser.add_argument(
        "--pairs",
        type=Path,
        help="Archivo JSON con lista de pares: [{\"ref\":\"...\",\"actual\":\"...\"}]",
    )
    parser.add_argument("--tolerance", type=float, default=1e-6, help="Tolerancia relativa (default 1e-6)")
    args = parser.parse_args()

    if not args.pairs and (args.ref is None or args.actual is None):
        parser.error("Debes usar --pairs o bien --ref y --actual.")

    if args.pairs:
        if not args.pairs.exists():
            print(f"[ERROR] No existe archivo de pares: {args.pairs}")
            return 1
        pairs = _load_json(args.pairs)
        if not isinstance(pairs, list):
            print("[ERROR] --pairs debe contener una lista JSON.")
            return 1
        failures = 0
        for item in pairs:
            ref_path = Path(item["ref"])
            actual_path = Path(item["actual"])
            failures += _run_pair(ref_path, actual_path, args.tolerance)
        return 0 if failures == 0 else 1

    assert args.ref is not None and args.actual is not None
    return _run_pair(args.ref, args.actual, args.tolerance)


if __name__ == "__main__":
    sys.exit(main())
