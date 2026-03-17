"""CLI para ejecutar el pipeline OSeMOSYS desde terminal.

Orígenes soportados: directorio de CSVs, archivo Excel o escenario en BD.
No modifica el pipeline ni la app; solo invoca osemosys_core y muestra resultado.

Requisito: ejecutar con el venv del proyecto activado (p. ej. desde raíz del repo:
  .\\.venv\\Scripts\\Activate.ps1
  cd backend
  python scripts/run_osemosys_cli.py csv "C:/ruta/al/CSV" [--solver glpk] [--lp]

Uso (desde backend/ con venv activo):
  python scripts/run_osemosys_cli.py csv "C:/ruta/al/CSV" [--solver glpk] [--lp] [--output-dir resultados]
  python scripts/run_osemosys_cli.py excel "C:/ruta/al/archivo.xlsm" [--sheet Parameters] [--output-dir resultados]
  python scripts/run_osemosys_cli.py db 1 [--solver glpk] [--output-dir resultados]

Con --output-dir se crea esa carpeta con CSVs de resultados (dispatch, new_capacity,
unmet_demand, annual_emissions, summary, simulation_result.json), como en el notebook.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from app.simulation.osemosys_core import (
        run_osemosys_from_csv_dir,
        run_osemosys_from_db,
        run_osemosys_from_excel,
    )
except ModuleNotFoundError as e:
    print(
        "ERROR: Faltan dependencias del proyecto. Activa el venv antes de ejecutar,\n"
        "por ejemplo desde la raíz del repo:\n"
        "  .\\.venv\\Scripts\\Activate.ps1\n"
        "  cd backend\n"
        "  python scripts/run_osemosys_cli.py ...\n"
        f"Detalle: {e}",
        file=sys.stderr,
    )
    sys.exit(1)


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Ejecutar pipeline OSeMOSYS: desde BD, Excel o directorio de CSVs.",
    )
    sub = parser.add_subparsers(dest="source", required=True, help="Origen de los datos")

    # Origen: directorio de CSVs
    p_csv = sub.add_parser("csv", help="Directorio con CSVs ya generados")
    p_csv.add_argument("csv_dir", type=Path, help="Ruta al directorio de CSVs")
    p_csv.add_argument("--solver", default="glpk", choices=("glpk", "highs"))
    p_csv.add_argument("--lp", action="store_true", help="Generar archivo .lp")
    p_csv.add_argument("--lp-dir", type=Path, default=None, help="Carpeta para el .lp (default: csv_dir)")
    p_csv.add_argument("--lp-name", default="osemosys", help="Nombre base del .lp")
    p_csv.add_argument("--output-dir", "-o", type=Path, default=None, help="Carpeta base para CSVs de resultados; cada corrida crea una subcarpeta run_YYYYMMDD_HHMMSS")
    p_csv.add_argument("--overwrite", action="store_true", help="Escribir en --output-dir sin subcarpeta con timestamp (sobrescribe)")

    # Origen: archivo Excel
    p_excel = sub.add_parser("excel", help="Archivo Excel SAND (.xlsm/.xlsx)")
    p_excel.add_argument("excel_path", type=Path, help="Ruta al Excel")
    p_excel.add_argument("--solver", default="glpk", choices=("glpk", "highs"))
    p_excel.add_argument("--sheet", default="Parameters", help="Nombre de la hoja")
    p_excel.add_argument("--div", type=int, default=1, help="Divisor timeslices")
    p_excel.add_argument("--lp", action="store_true", help="Generar archivo .lp")
    p_excel.add_argument("--output-dir", "-o", type=Path, default=None, help="Carpeta base para CSVs; cada corrida crea subcarpeta run_YYYYMMDD_HHMMSS")
    p_excel.add_argument("--overwrite", action="store_true", help="Escribir en --output-dir sin timestamp (sobrescribe)")

    # Origen: base de datos (escenario)
    p_db = sub.add_parser("db", help="Escenario desde PostgreSQL")
    p_db.add_argument("scenario_id", type=int, help="ID del escenario")
    p_db.add_argument("--solver", default="glpk", choices=("glpk", "highs"))
    p_db.add_argument("--lp", action="store_true", help="Generar archivo .lp")
    p_db.add_argument("--output-dir", "-o", type=Path, default=None, help="Carpeta base para CSVs; cada corrida crea subcarpeta run_YYYYMMDD_HHMMSS")
    p_db.add_argument("--overwrite", action="store_true", help="Escribir en --output-dir sin timestamp (sobrescribe)")

    args = parser.parse_args()

    if args.source == "csv":
        if not args.csv_dir.is_dir():
            print(f"ERROR: No existe el directorio: {args.csv_dir}")
            return 1
        result = run_osemosys_from_csv_dir(
            args.csv_dir,
            solver_name=args.solver,
            generate_lp=args.lp,
            lp_dir=args.lp_dir,
            lp_basename=args.lp_name,
        )
    elif args.source == "excel":
        if not args.excel_path.is_file():
            print(f"ERROR: No existe el archivo: {args.excel_path}")
            return 1
        result = run_osemosys_from_excel(
            args.excel_path,
            solver_name=args.solver,
            sheet_name=args.sheet,
            div=args.div,
            generate_lp=args.lp,
        )
    else:  # db
        from app.db.session import SessionLocal
        db = SessionLocal()
        try:
            result = run_osemosys_from_db(
                db,
                scenario_id=args.scenario_id,
                solver_name=args.solver,
                generate_lp=args.lp,
            )
        finally:
            db.close()

    print(f"Solver: {result['solver_name']}  Status: {result['solver_status']}")
    print(f"Objetivo: {result.get('objective_value', 0):,.2f}")

    output_dir = getattr(args, "output_dir", None)
    if output_dir is not None:
        from app.simulation.export_results import export_solution_to_folder
        overwrite = getattr(args, "overwrite", False)
        out_path = export_solution_to_folder(
            result, output_dir, write_json=True, use_timestamp_subdir=not overwrite
        )
        print(f"Resultados exportados a: {out_path}")

    if result.get("solver_status", "").upper() != "OPTIMAL":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main())
