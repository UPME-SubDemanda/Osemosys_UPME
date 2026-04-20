from __future__ import annotations

"""Tareas Celery para ejecución de jobs de simulación.

Este módulo traduce el estado de infraestructura (task ejecutándose/fallando)
a estado de dominio (`simulation_job`) persistido en base de datos.
"""

import logging
import shutil
from pathlib import Path

from celery.signals import task_failure
from sqlalchemy import func, update

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import SimulationJob
from app.repositories.simulation_repository import SimulationRepository
from app.simulation.celery_app import celery_app
from app.simulation.pipeline import run_pipeline, run_pipeline_from_csv

logger = logging.getLogger(__name__)


def _resolve_csv_upload_cleanup_root(input_ref: str | None) -> Path | None:
    if not input_ref:
        return None

    uploads_root = (Path(get_settings().simulation_artifacts_dir).resolve() / "csv_upload_jobs").resolve()
    candidate = Path(str(input_ref)).resolve()
    try:
        relative = candidate.relative_to(uploads_root)
    except ValueError:
        return None
    if not relative.parts:
        return None
    return uploads_root / relative.parts[0]


def _cleanup_csv_upload_artifacts(job: SimulationJob | None) -> None:
    if job is None or getattr(job, "input_mode", "SCENARIO") != "CSV_UPLOAD":
        return

    cleanup_root = _resolve_csv_upload_cleanup_root(getattr(job, "input_ref", None))
    if cleanup_root is None:
        return

    try:
        shutil.rmtree(cleanup_root)
        logger.info("Artefactos CSV temporales eliminados para job %s en %s", job.id, cleanup_root)
    except FileNotFoundError:
        return
    except Exception:
        logger.warning(
            "No se pudieron eliminar artefactos CSV temporales del job %s en %s",
            getattr(job, "id", "?"),
            cleanup_root,
            exc_info=True,
        )


def _is_worker_lost_error(exception: BaseException | None) -> bool:
    if exception is None:
        return False
    text = f"{type(exception).__name__}: {exception}".lower()
    return (
        "workerlosterror" in text
        or "worker exited prematurely" in text
        or "signal 9" in text
        or "sigkill" in text
    )


def _fail_running_job(db, *, job: SimulationJob, reason: str) -> None:
    if job.status != "RUNNING":
        return
    job.status = "FAILED"
    job.finished_at = func.now()
    job.error_message = reason
    SimulationRepository.add_event(
        db,
        job_id=job.id,
        event_type="ERROR",
        stage="run",
        message=reason,
        progress=job.progress,
    )
    db.commit()


def _mark_failed_by_task_or_job_id(
    *,
    task_id: str | None,
    job_id: int | None,
    reason: str,
) -> bool:
    with SessionLocal() as db:
        job: SimulationJob | None = None
        if task_id:
            job = (
                db.query(SimulationJob)
                .filter(
                    SimulationJob.celery_task_id == task_id,
                    SimulationJob.status == "RUNNING",
                )
                .first()
            )
        if job is None and job_id is not None:
            job = (
                db.query(SimulationJob)
                .filter(SimulationJob.id == job_id, SimulationJob.status == "RUNNING")
                .first()
            )
        if job is None:
            return False
        _fail_running_job(db, job=job, reason=reason)
        return True


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
            job = SimulationRepository.get_job_by_id(db, job_id=job_id)
            if not job:
                return
            if getattr(job, "input_mode", "SCENARIO") == "CSV_UPLOAD":
                run_pipeline_from_csv(db, job_id=job_id)
            else:
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
    finally:
        with SessionLocal() as db:
            job = SimulationRepository.get_job_by_id(db, job_id=job_id)
            _cleanup_csv_upload_artifacts(job)
        with SessionLocal() as db:
            from app.services.simulation_service import SimulationService

            SimulationService.dispatch_pending_jobs(db)


@task_failure.connect
def handle_worker_lost_failure(
    sender=None,
    task_id: str | None = None,
    exception: BaseException | None = None,
    args: tuple | None = None,
    **_: object,
) -> None:
    sender_name = getattr(sender, "name", None)
    if sender_name != run_simulation_job.name:
        return
    if not _is_worker_lost_error(exception):
        return

    job_id: int | None = None
    if args and len(args) > 0 and isinstance(args[0], int):
        job_id = args[0]

    reason = (
        f"WorkerLostError detectado por Celery: {exception}. "
        "El proceso del worker fue terminado abruptamente."
    )
    updated = _mark_failed_by_task_or_job_id(
        task_id=task_id,
        job_id=job_id,
        reason=reason,
    )
    if not updated:
        logger.warning(
            "No se encontró job RUNNING para task_id=%s job_id=%s tras WorkerLostError",
            task_id,
            job_id,
        )


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
