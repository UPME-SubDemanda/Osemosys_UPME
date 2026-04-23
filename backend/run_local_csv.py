"""
Script para correr la simulación OSeMOSYS desde un directorio de CSVs.

Uso:
    cd backend
    python3 run_local_csv.py

Si el modelo resulta infactible, se ejecuta automáticamente un análisis
adicional (mapeo a parámetros OSeMOSYS + IIS con HiGHS cuando aplica) y se
escribe un JSON con el reporte completo en `tmp/infeasibility-reports/`.
"""

import os
from datetime import datetime
from pathlib import Path

# Sobreescribir DATABASE_URL para apuntar a localhost (puerto expuesto por Docker).
# Este pipeline no usa BD, pero algunos imports del paquete `app` pueden inicializar
# la sesión al cargarse, así que mantenemos la misma configuración que run_local.py.
os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://osemosys:osemosys@localhost:55432/osemosys"
)

# Stream del log nativo del solver (HiGHS/GLPK) a stdout para ver progreso.
# Equivalente a pasar `tee=True` en pyomo.SolverFactory.solve(...). En el
# pipeline productivo esto se controla con la env SIM_SOLVER_TEE (default False).
os.environ.setdefault("SIM_SOLVER_TEE", "true")

from app.simulation.core.infeasibility_analysis import (  # noqa: E402
    analyze,
    print_report_console,
    write_report_json,
)
from app.simulation.osemosys_core import run_osemosys_from_csv_dir  # noqa: E402

# ── Parámetros de la simulación ──────────────────────────────────────
CSV_DIR = "/Users/davidbedoya0/Downloads/CSV_Cleaned_debug"      # Directorio con los CSVs (REGION.csv, YEAR.csv, TECHNOLOGY.csv, etc.)
CSV_DIR = "/Users/davidbedoya0/Downloads/CSV_Cleaned-2"      # Directorio con los CSVs (REGION.csv, YEAR.csv, TECHNOLOGY.csv, etc.)
CSV_DIR = "temp/PD_15042026"      # Directorio con los CSVs (REGION.csv, YEAR.csv, TECHNOLOGY.csv, etc.)
SOLVER_NAME = "highs"           # "glpk" o "highs"
GENERATE_LP = False            # Generar archivo LP del modelo
LP_DIR = None                  # Directorio para el archivo LP (None = usa CSV_DIR)
LP_BASENAME = "osemosys"       # Nombre base del archivo .lp

# ── Parámetros del análisis de infactibilidad ────────────────────────
RUN_INFEASIBILITY_ANALYSIS = True
INFEASIBILITY_REPORT_DIR = Path("tmp/infeasibility-reports")
INFEASIBILITY_TOP_N = 20

# Diccionario usado para pasar `instance` y `solver` desde el hook del solver
# hasta el análisis posterior sin modificar la firma del pipeline.
_captured: dict = {}


def on_stage(stage: str, progress: float) -> None:
    """Callback de progreso (se imprime en consola)."""
    print(f"  [{progress:5.1f}%] {stage}")


def on_solver_finished(instance, solver, solver_result, solution) -> None:  # noqa: ARG001
    """Captura la instancia Pyomo y el solver al terminar el solve.

    Se usa luego para correr IIS con HiGHS sobre el mismo modelo. Para depurar
    con pdb puedes descomentar la línea de abajo y entrar aquí antes del
    análisis.
    """
    # import pdb ; pdb.set_trace()
    _captured["instance"] = instance
    _captured["solver"] = solver


def _is_infeasible(solution: dict) -> bool:
    status = str(solution.get("solver_status") or "").lower()
    if "infeasible" in status or "infactible" in status:
        return True
    diagnostics = solution.get("infeasibility_diagnostics") or {}
    if isinstance(diagnostics, dict):
        if diagnostics.get("constraint_violations") or diagnostics.get("var_bound_conflicts"):
            return True
    return False


if __name__ == "__main__":
    print("Iniciando simulación desde directorio de CSVs...")
    print(f"  CSV dir   : {CSV_DIR}")
    print(f"  Solver    : {SOLVER_NAME}")
    print()

    print("Ejecutando OSeMOSYS...")
    result = run_osemosys_from_csv_dir(
        CSV_DIR,
        solver_name=SOLVER_NAME,
        on_stage=on_stage,
        generate_lp=GENERATE_LP,
        lp_dir=LP_DIR,
        lp_basename=LP_BASENAME,
        on_solver_finished=on_solver_finished,
    )

    print()
    print("Simulación completada.")
    print(f"  Estado   : {result.get('solver_status')}")
    print(f"  Objetivo : {result.get('objective_value')}")

    if RUN_INFEASIBILITY_ANALYSIS and _is_infeasible(result):
        report = analyze(
            solution=result,
            instance=_captured.get("instance"),
            solver=_captured.get("solver"),
            csv_dir=CSV_DIR,
            top_n=INFEASIBILITY_TOP_N,
        )
        print_report_console(report, top_n=10)

        INFEASIBILITY_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = INFEASIBILITY_REPORT_DIR / (
            f"infeasibility_{datetime.now():%Y%m%d_%H%M%S}.json"
        )
        write_report_json(report, out_path)
        print(f"Reporte de infactibilidad guardado en: {out_path.resolve()}")
