"""Importa el Excel SAND (hoja Parameters), ejecuta la simulación y guarda el resultado.

Permite probar los mismos datos en la app y en el notebook Jupyter y comparar resultados.

Uso (desde backend, con venv activo o en contenedor):
  python scripts/run_sand_excel_test.py
  python scripts/run_sand_excel_test.py --excel "C:/ruta/al/SAND_04_02_2026.xlsm"
  python scripts/run_sand_excel_test.py --excel "C:/ruta/al/archivo.xlsm" --replace --solver glpk

Requisitos:
  - Usuario "seed" existente en la BD (scripts/seed.py).
  - Archivo .xlsm o .xlsx con hoja "Parameters" en formato SAND (columna parameter, columnas de año, etc.).

Salida:
  - Crea o actualiza escenario "SAND_04_02_2026" con los datos del Excel.
  - Ejecuta la simulación (highs por defecto; use --solver glpk para alinear con notebook).
  - Escribe JSON en backend/tmp/sand_04_02_2026_result.json para comparar con el notebook.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import SessionLocal
from app.models import OsemosysParamValue, Scenario, User
from app.services.official_import_service import OfficialImportService
from app.services.scenario_service import ScenarioService
from app.services.sand_notebook_preprocess import run_notebook_preprocess
from app.simulation.osemosys_core import run_osemosys_from_db

DEFAULT_EXCEL = (
    r"C:\Users\jchav\OneDrive - Universidad de los Andes\Documentos\Trabajo UPME\Archivos osmosys\Excel\SAND_04_02_2026.xlsm"
)
SCENARIO_NAME = "SAND_04_02_2026"
SHEET_NAME = "Parameters"
OUTPUT_FILENAME = "sand_04_02_2026_result.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Importar Excel Parameters, ejecutar simulación y guardar resultado")
    parser.add_argument(
        "--excel",
        type=Path,
        default=Path(DEFAULT_EXCEL),
        help=f"Ruta al archivo .xlsm/.xlsx (default: {DEFAULT_EXCEL})",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Si el escenario ya existe, borrar sus datos OSeMOSYS y reimportar",
    )
    parser.add_argument(
        "--solver",
        choices=("highs", "glpk"),
        default="highs",
        help="Solver a usar (glpk para alinear con notebook por defecto)",
    )
    args = parser.parse_args()

    excel_path = args.excel
    if not excel_path.is_file():
        print(f"[ERROR] No existe el archivo Excel: {excel_path}")
        print("        Usa --excel para indicar la ruta correcta.")
        return 1

    content = excel_path.read_bytes()
    filename = excel_path.name

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.username == "seed")).scalar_one_or_none()
        if not user:
            print("[ERROR] No existe usuario 'seed'. Ejecuta scripts/seed.py primero.")
            return 1

        scenario = session.execute(
            select(Scenario).where(
                Scenario.name == SCENARIO_NAME,
                Scenario.is_template.is_(False),
            )
        ).scalar_one_or_none()

        if scenario and args.replace:
            sid = scenario.id
            deleted = session.query(OsemosysParamValue).filter(OsemosysParamValue.id_scenario == sid).delete()
            session.commit()
            scenario = session.execute(select(Scenario).where(Scenario.id == sid)).scalar_one()
            print(f"  Datos OSeMOSYS del escenario existente borrados ({deleted} filas).")

        if not scenario:
            scenario = ScenarioService.create(
                session,
                current_user=user,
                name=SCENARIO_NAME,
                description="Importado desde Excel SAND (hoja Parameters) para prueba y comparación con notebook",
                edit_policy="OWNER_ONLY",
                is_template=False,
            )
            print(f"  Escenario creado: {scenario.name} (id={scenario.id})")
        else:
            print(f"  Usando escenario existente: {scenario.name} (id={scenario.id})")

        print(f"  Importando hoja '{SHEET_NAME}' desde {filename}...")
        import_result = OfficialImportService.import_xlsm(
            session,
            filename=filename,
            content=content,
            imported_by=user.username,
            selected_sheet_name=SHEET_NAME,
            scenario_id_override=scenario.id,
        )
        print(f"  Import: {import_result.get('inserted', 0)} insertados, {import_result.get('updated', 0)} actualizados, {import_result.get('skipped', 0)} omitidos.")
        if import_result.get("warnings"):
            for w in import_result["warnings"][:10]:
                print(f"    [aviso] {w}")
            if len(import_result["warnings"]) > 10:
                print(f"    ... y {len(import_result['warnings']) - 10} avisos más.")

        print(f"  Aplicando preprocesamiento tipo notebook (paridad UPME)...")
        run_notebook_preprocess(
            session,
            scenario.id,
            filter_by_sets=True,
            complete_matrices=False,
            emission_ratios_at_input=True,
            generate_udc_matrices=False,
        )
        session.commit()
        print(f"  Ejecutando simulación (solver={args.solver})...")
        result = run_osemosys_from_db(
            session,
            scenario_id=scenario.id,
            solver_name=args.solver,
        )

    obj = float(result.get("objective_value", 0.0))
    total_demand = float(result.get("total_demand", 0.0))
    total_dispatch = float(result.get("total_dispatch", 0.0))
    total_unmet = float(result.get("total_unmet", 0.0))
    coverage = float(result.get("coverage_ratio", 0.0))
    status = result.get("solver_status", "?")

    print("\n--- Resumen (comparar con notebook) ---")
    print(f"  objective_value : {obj}")
    print(f"  total_demand    : {total_demand}")
    print(f"  total_dispatch  : {total_dispatch}")
    print(f"  total_unmet     : {total_unmet}")
    print(f"  coverage_ratio  : {coverage}")
    print(f"  solver_status   : {status}")
    print("--------------------------------------\n")

    out_dir = PROJECT_ROOT / "tmp"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / OUTPUT_FILENAME
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Resultado guardado en: {out_path}")
    print("\nComparación con Jupyter:")
    print("  1. En el notebook, usa el mismo archivo y hoja 'Parameters', solver glpk si usaste --solver glpk.")
    print("  2. Anota objective_value y totales del notebook o exporta a JSON.")
    print("  3. python scripts/compare_results.py --ref referencia_notebook.json --actual tmp/sand_04_02_2026_result.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
