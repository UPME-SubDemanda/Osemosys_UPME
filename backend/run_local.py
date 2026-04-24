"""
Script para correr la simulación OSeMOSYS desde la base de datos local.

Uso:
    cd backend
    python3 run_local.py

Modo round-trip (mismo ``run_data_processing`` que el paso 1 de ``run_osemosys_from_db``):
    RUN_MODE=roundtrip python3 run_local.py

    Crea un escenario desde el Excel (por defecto ``<repo>/SAND_integrado_PA_MR_20_04.xlsx``),
    escribe los CSV del pipeline en ``tmp/run_local_pipeline_csv``, importa esos CSV en un
    segundo escenario y compara re-exports.

Variables de entorno útiles:
    ROUNDTRIP_EXCEL           Ruta al .xlsx
    ROUNDTRIP_PIPELINE_CSV_DIR  Carpeta de salida de ``run_data_processing`` (default tmp/...)
    ROUNDTRIP_SEED_USER       Usuario BD (default seed)
    ROUNDTRIP_KEEP_TEMP       1/0 conservar carpetas temporales de re-export (default 1)
    ROUNDTRIP_PRESERVE_TIMESLICES  1 = import Excel sin colapsar timeslices
    OSEMOSYS_REPO_ROOT        Raíz del repo si solo montas ``backend`` en Docker (ej. /repo)

Ejemplo Docker: monta el repo en ``/repo`` (solo lectura), el backend en ``/app``, define
``OSEMOSYS_REPO_ROOT=/repo``, ``DATABASE_URL`` hacia el servicio ``db`` y ``RUN_LOCAL_MODE=roundtrip``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
# En Docker suele montarse solo ``backend`` en ``/app``; entonces ``parent`` no es el repo.
# Opcional: ``OSEMOSYS_REPO_ROOT=/ruta/al/repo`` (o define ``ROUNDTRIP_EXCEL`` directamente).
REPO_ROOT = Path(os.environ["OSEMOSYS_REPO_ROOT"]) if os.environ.get("OSEMOSYS_REPO_ROOT") else BACKEND_DIR.parent

# Sobreescribir DATABASE_URL para apuntar a localhost (puerto expuesto por Docker)
# en lugar de 'db' (nombre del servicio Docker, solo accesible dentro de la red Docker).
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://osemosys:osemosys@localhost:55432/osemosys",
)

# ── Modo de ejecución ─────────────────────────────────────────────────
# "solve"     → solo resolver con SCENARIO_ID (comportamiento clásico).
# "roundtrip" → prueba Excel → run_data_processing → import CSV → comparar exports.
RUN_MODE = os.environ.get("RUN_LOCAL_MODE", "solve").strip().lower()

# Excel por defecto en la raíz del repo (mismo criterio que README / scripts).
ROUNDTRIP_EXCEL = Path(
    os.environ.get("ROUNDTRIP_EXCEL", str(REPO_ROOT / "SAND_integrado_PA_MR_20_04.xlsx"))
)

# CSV generados por ``run_data_processing`` (persistente para inspección / run_local_csv).
PIPELINE_CSV_DIR = Path(
    os.environ.get("ROUNDTRIP_PIPELINE_CSV_DIR", str(BACKEND_DIR / "tmp" / "run_local_pipeline_csv"))
)

ROUNDTRIP_SEED_USER = os.environ.get("ROUNDTRIP_SEED_USER", "seed")
ROUNDTRIP_KEEP_TEMP = os.environ.get("ROUNDTRIP_KEEP_TEMP", "1").strip().lower() in (
    "1",
    "true",
    "yes",
)
ROUNDTRIP_PRESERVE_TIMESLICES = os.environ.get("ROUNDTRIP_PRESERVE_TIMESLICES", "").strip().lower() in (
    "1",
    "true",
    "yes",
)

# ── Parámetros de la simulación (modo solve) ──────────────────────────
SCENARIO_ID = 2  # ID del escenario en la base de datos
SOLVER_NAME = "glpk"  # "glpk" o "highs"
GENERATE_LP = False  # Generar archivo LP del modelo
LP_DIR = None  # Directorio para el archivo LP (None = temporal)


def on_stage(stage: str, progress: float) -> None:
    """Callback de progreso (se imprime en consola)."""
    print(f"  [{progress:5.1f}%] {stage}")


def _run_roundtrip() -> int:
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    from scripts.roundtrip_excel_csv_compare import run_excel_csv_roundtrip

    excel = ROUNDTRIP_EXCEL.resolve()
    if not excel.is_file():
        print(
            f"ERROR: Modo roundtrip pero no existe el Excel: {excel}\n"
            "Coloca SAND_integrado_PA_MR_20_04.xlsx en la raíz del repo o define ROUNDTRIP_EXCEL.",
            file=sys.stderr,
        )
        return 2

    PIPELINE_CSV_DIR.mkdir(parents=True, exist_ok=True)
    print("Modo roundtrip (Excel → run_data_processing → CSV en disco → import → comparar).")
    print(f"  Excel: {excel}")
    print(f"  CSV del pipeline: {PIPELINE_CSV_DIR.resolve()}")
    print(f"  preserve_timeslices: {ROUNDTRIP_PRESERVE_TIMESLICES}")
    print()

    return run_excel_csv_roundtrip(
        excel,
        seed_user=ROUNDTRIP_SEED_USER,
        preserve_timeslices=ROUNDTRIP_PRESERVE_TIMESLICES,
        keep_temp=ROUNDTRIP_KEEP_TEMP,
        pipeline_csv_dir=PIPELINE_CSV_DIR,
    )


if __name__ == "__main__":
    if RUN_MODE in ("roundtrip", "excel_csv", "rt"):
        raise SystemExit(_run_roundtrip())

    from app.db.session import SessionLocal  # noqa: E402
    from app.simulation.osemosys_core import run_osemosys_from_db  # noqa: E402

    print("Iniciando simulación desde base de datos...")
    print(f"  Escenario : {SCENARIO_ID}")
    print(f"  Solver    : {SOLVER_NAME}")
    print()

    with SessionLocal() as db:

        print("Ejecutando OSeMOSYS...")
        # import pdb ; pdb.set_trace()
        result = run_osemosys_from_db(
            db,
            scenario_id=SCENARIO_ID,
            solver_name=SOLVER_NAME,
            on_stage=on_stage,
            generate_lp=GENERATE_LP,
            lp_dir=LP_DIR,
        )

    print()
    print("Simulación completada.")
    print(f"  Resultado: {result}")
