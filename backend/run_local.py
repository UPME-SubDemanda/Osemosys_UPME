"""
Script para correr la simulación OSeMOSYS desde la base de datos local.

Uso:
    cd backend
    python3 run_local.py
"""

import os

# Sobreescribir DATABASE_URL para apuntar a localhost (puerto expuesto por Docker)
# en lugar de 'db' (nombre del servicio Docker, solo accesible dentro de la red Docker).
os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://osemosys:osemosys@localhost:55432/osemosys"
)

from app.db.session import SessionLocal  # noqa: E402
from app.simulation.osemosys_core import run_osemosys_from_db  # noqa: E402

# ── Parámetros de la simulación ──────────────────────────────────────
SCENARIO_ID = 2                # ID del escenario en la base de datos
SOLVER_NAME = "glpk"           # "glpk" o "highs"
GENERATE_LP = False            # Generar archivo LP del modelo
LP_DIR = None                  # Directorio para el archivo LP (None = temporal)


def on_stage(stage: str, progress: float) -> None:
    """Callback de progreso (se imprime en consola)."""
    print(f"  [{progress:5.1f}%] {stage}")


if __name__ == "__main__":
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
