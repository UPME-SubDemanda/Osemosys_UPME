from __future__ import annotations

"""Tareas Celery para ejecución de jobs de simulación.

Este módulo traduce el estado de infraestructura (task ejecutándose/fallando)
a estado de dominio (`simulation_job`) persistido en base de datos.
"""

from sqlalchemy import func, update

from app.db.session import SessionLocal
from app.models import SimulationJob
from app.repositories.simulation_repository import SimulationRepository
from app.simulation.celery_app import celery_app
from app.simulation.pipeline import run_pipeline


@celery_app.task(name="app.simulation.tasks.run_simulation_job", bind=True)
def run_simulation_job(self, job_id: int) -> None:
    """Ejecuta un job de simulación en contexto worker.

    Args:
        self: Instancia de task Celery (no usada directamente en la lógica actual).
        job_id: Identificador del job persistido en BD.

    Flujo:
        1. Marca job en `RUNNING`.
        2. Ejecuta pipeline matemático.
        3. Persiste estado terminal (`SUCCEEDED`/`FAILED`).
        4. Registra eventos para observabilidad operacional.

    Edge cases:
        - Job no encontrado (mensaje obsoleto en cola).
        - Job previamente finalizado/cancelado.
        - Cancelación cooperativa durante pipeline.

    Rendimiento:
        - CPU-bound en `run_pipeline` durante etapa de solve.
        - I/O-bound en escrituras de eventos y actualización de estado.
    """
    with SessionLocal() as db:
        transitioned = db.execute(
            update(SimulationJob)
            .where(SimulationJob.id == job_id, SimulationJob.status == "QUEUED")
            .values(status="RUNNING", started_at=func.now(), progress=1.0)
        ).rowcount
        db.commit()

        if not transitioned:
            job = SimulationRepository.get_job_by_id(db, job_id=job_id)
            if not job:
                return
            if job.status in ("RUNNING", "CANCELLED", "SUCCEEDED", "FAILED"):
                return
            return

        job = SimulationRepository.get_job_by_id(db, job_id=job_id)
        if not job:
            return
        SimulationRepository.add_event(
            db,
            job_id=job_id,
            event_type="INFO",
            stage="start",
            message="Simulación iniciada en worker.",
            progress=job.progress,
        )
        db.commit()

    try:
        with SessionLocal() as db:
            run_pipeline(db, job_id=job_id)
            job = SimulationRepository.get_job_by_id(db, job_id=job_id)
            if not job:
                return
            if job.status == "CANCELLED":
                return
            job.status = "SUCCEEDED"
            job.progress = 100.0
            job.finished_at = func.now()
            SimulationRepository.add_event(
                db,
                job_id=job_id,
                event_type="INFO",
                stage="end",
                message="Simulacion finalizada correctamente.",
                progress=100.0,
            )
            db.commit()
    except RuntimeError as exc:
        if str(exc) == "JOB_CANCELLED":
            return
        with SessionLocal() as db:
            job = SimulationRepository.get_job_by_id(db, job_id=job_id)
            if job:
                job.status = "FAILED"
                job.finished_at = func.now()
                job.error_message = str(exc)
                SimulationRepository.add_event(
                    db,
                    job_id=job_id,
                    event_type="ERROR",
                    stage="run",
                    message=str(exc),
                    progress=job.progress,
                )
                db.commit()
    except Exception as exc:  # pragma: no cover - seguridad ante fallos inesperados
        with SessionLocal() as db:
            job = SimulationRepository.get_job_by_id(db, job_id=job_id)
            if job:
                job.status = "FAILED"
                job.finished_at = func.now()
                job.error_message = str(exc)
                SimulationRepository.add_event(
                    db,
                    job_id=job_id,
                    event_type="ERROR",
                    stage="run",
                    message=str(exc),
                    progress=job.progress,
                )
                db.commit()


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Garantizar transición consistente de estado de jobs desde la capa de worker.
#
# Posibles mejoras:
# - Incorporar idempotencia explícita por `celery_task_id` para retries/replays.
# - Añadir taxonomía de errores (solver, datos, infraestructura) para observabilidad.
#
# Riesgos en producción:
# - Fallos entre solve exitoso y commit final pueden dejar artefacto generado pero
#   estado no actualizado, generando incoherencia temporal.
# - Reintentos automáticos no configurados podrían ocultar fallos transitorios.
#
# Escalabilidad:
# - El throughput está limitado por CPU disponible y concurrencia del worker.
