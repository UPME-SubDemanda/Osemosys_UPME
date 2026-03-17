"""Punto de entrada para ejecución programática de simulaciones."""

from __future__ import annotations

from app.db.session import SessionLocal
from app.simulation.pipeline import run_pipeline


def run_simulation_sync(job_id: int) -> str:
    """Ejecuta una simulación de forma síncrona (útil para debugging/tests)."""
    with SessionLocal() as db:
        return run_pipeline(db, job_id=job_id)


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Ofrecer entrada síncrona para debugging, pruebas y ejecución manual.
#
# Posibles mejoras:
# - Permitir inyección de sesión/transaction para tests más finos.
#
# Riesgos en producción:
# - No debe usarse como camino principal en tráfico concurrente.
#
# Escalabilidad:
# - Ejecución bloqueante, CPU-bound durante solve.
