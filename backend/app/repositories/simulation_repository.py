"""Repositorio de jobs/eventos para ejecución de simulaciones."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import Scenario, SimulationJob, SimulationJobEvent, User


ACTIVE_STATUSES = ("QUEUED", "RUNNING")


class SimulationRepository:
    """Acceso a datos de la cola de simulaciones."""

    @staticmethod
    def get_scenario(db: Session, *, scenario_id: int) -> Scenario | None:
        """Obtiene escenario asociado al job."""
        return db.get(Scenario, scenario_id)

    @staticmethod
    def count_user_active_jobs(db: Session, *, user_id: uuid.UUID) -> int:
        """Cuenta jobs activos del usuario (`QUEUED` + `RUNNING`)."""
        stmt = select(func.count()).select_from(SimulationJob).where(
            and_(SimulationJob.user_id == user_id, SimulationJob.status.in_(ACTIVE_STATUSES))
        )
        return int(db.scalar(stmt) or 0)

    @staticmethod
    def create_job(
        db: Session, *, user_id: uuid.UUID, scenario_id: int, solver_name: str = "highs"
    ) -> SimulationJob:
        """Crea job en estado `QUEUED`."""
        job = SimulationJob(
            user_id=user_id,
            scenario_id=scenario_id,
            solver_name=solver_name,
            status="QUEUED",
            progress=0.0,
        )
        db.add(job)
        return job

    @staticmethod
    def get_job_for_user(db: Session, *, job_id: int, user_id: uuid.UUID) -> SimulationJob | None:
        """Obtiene job por id restringido al propietario."""
        stmt = select(SimulationJob).where(SimulationJob.id == job_id, SimulationJob.user_id == user_id)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_job_visible(
        db: Session,
        *,
        job_id: int,
    ) -> tuple[SimulationJob, str | None, str | None] | None:
        """Obtiene job visible globalmente con username y nombre de escenario."""
        stmt = (
            select(
                SimulationJob,
                User.username.label("username"),
                Scenario.name.label("scenario_name"),
            )
            .join(User, User.id == SimulationJob.user_id)
            .join(Scenario, Scenario.id == SimulationJob.scenario_id)
            .where(SimulationJob.id == job_id)
        )
        row = db.execute(stmt).one_or_none()
        if row is None:
            return None
        return row[0], row.username, row.scenario_name

    @staticmethod
    def get_job_by_id(db: Session, *, job_id: int) -> SimulationJob | None:
        """Obtiene job por id sin control de ownership."""
        return db.get(SimulationJob, job_id)

    @staticmethod
    def list_jobs_for_user(
        db: Session,
        *,
        user_id: uuid.UUID,
        status: str | None,
        row_offset: int,
        limit: int,
    ) -> tuple[list[SimulationJob], int]:
        """Lista jobs de un usuario con filtro opcional por estado."""
        where = SimulationJob.user_id == user_id
        if status:
            where = and_(where, SimulationJob.status == status)

        total = int(db.scalar(select(func.count()).select_from(SimulationJob).where(where)) or 0)
        stmt = (
            select(SimulationJob)
            .where(where)
            .order_by(SimulationJob.queued_at.desc())
            .offset(row_offset)
            .limit(limit)
        )
        items = db.execute(stmt).scalars().all()
        return list(items), total

    @staticmethod
    def list_jobs(
        db: Session,
        *,
        scope: str,
        user_id: uuid.UUID,
        status: str | None,
        username: str | None,
        scenario_id: int | None,
        solver_name: str | None,
        row_offset: int,
        limit: int,
    ) -> tuple[list[tuple[SimulationJob, str | None, str | None]], int]:
        """Lista jobs visibles con metadatos de usuario y escenario."""
        stmt = (
            select(
                SimulationJob,
                User.username.label("username"),
                Scenario.name.label("scenario_name"),
            )
            .join(User, User.id == SimulationJob.user_id)
            .join(Scenario, Scenario.id == SimulationJob.scenario_id)
        )

        filters = []
        if scope == "mine":
            filters.append(SimulationJob.user_id == user_id)
        if status:
            filters.append(SimulationJob.status == status)
        if username:
            filters.append(User.username.ilike(f"%{username}%"))
        if scenario_id is not None:
            filters.append(SimulationJob.scenario_id == scenario_id)
        if solver_name:
            filters.append(SimulationJob.solver_name == solver_name)

        if filters:
            stmt = stmt.where(and_(*filters))

        count_stmt = (
            select(func.count())
            .select_from(SimulationJob)
            .join(User, User.id == SimulationJob.user_id)
            .join(Scenario, Scenario.id == SimulationJob.scenario_id)
        )
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        total = int(db.scalar(count_stmt) or 0)

        items = (
            db.execute(
                stmt.order_by(SimulationJob.queued_at.desc(), SimulationJob.id.desc())
                .offset(row_offset)
                .limit(limit)
            )
            .all()
        )
        return [(row[0], row.username, row.scenario_name) for row in items], total

    @staticmethod
    def count_overview(db: Session) -> dict[str, int]:
        """Conteos agregados para el tablero global."""
        queued_count = int(
            db.scalar(select(func.count()).select_from(SimulationJob).where(SimulationJob.status == "QUEUED")) or 0
        )
        running_count = int(
            db.scalar(select(func.count()).select_from(SimulationJob).where(SimulationJob.status == "RUNNING")) or 0
        )
        total_count = int(db.scalar(select(func.count()).select_from(SimulationJob)) or 0)
        return {
            "queued_count": queued_count,
            "running_count": running_count,
            "active_count": queued_count + running_count,
            "total_count": total_count,
        }

    @staticmethod
    def queue_position(db: Session, *, job_id: int) -> int:
        """Calcula posición de cola para jobs en `QUEUED`."""
        job = db.get(SimulationJob, job_id)
        if not job or job.status != "QUEUED":
            return 0
        stmt = select(func.count()).select_from(SimulationJob).where(
            SimulationJob.status == "QUEUED",
            SimulationJob.queued_at < job.queued_at,
        )
        ahead = int(db.scalar(stmt) or 0)
        return ahead + 1

    @staticmethod
    def add_event(
        db: Session,
        *,
        job_id: int,
        event_type: str,
        stage: str | None,
        message: str | None,
        progress: float | None,
    ) -> SimulationJobEvent:
        """Agrega evento de trazabilidad/progreso para un job."""
        event = SimulationJobEvent(
            job_id=job_id,
            event_type=event_type,
            stage=stage,
            message=message,
            progress=progress,
        )
        db.add(event)
        return event

    @staticmethod
    def list_events(
        db: Session, *, job_id: int, row_offset: int, limit: int
    ) -> tuple[list[SimulationJobEvent], int]:
        """Lista eventos de un job ordenados por creación ascendente."""
        total = int(
            db.scalar(select(func.count()).select_from(SimulationJobEvent).where(SimulationJobEvent.job_id == job_id))
            or 0
        )
        stmt = (
            select(SimulationJobEvent)
            .where(SimulationJobEvent.job_id == job_id)
            .order_by(SimulationJobEvent.created_at.asc())
            .offset(row_offset)
            .limit(limit)
        )
        items = db.execute(stmt).scalars().all()
        return list(items), total

    @staticmethod
    def list_stale_queued_without_task(
        db: Session, *, older_than_minutes: int, limit: int = 100
    ) -> list[SimulationJob]:
        """Lista jobs `QUEUED` sin `celery_task_id` con antigüedad mayor al umbral."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
        stmt = (
            select(SimulationJob)
            .where(
                SimulationJob.status == "QUEUED",
                SimulationJob.celery_task_id.is_(None),
                SimulationJob.queued_at < cutoff,
            )
            .order_by(SimulationJob.queued_at.asc())
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Persistencia de estado de ejecución y bitácora de eventos de simulación.
#
# Posibles mejoras:
# - `queue_position` puede migrar a estrategia con ranking/materialización.
# - Añadir índices compuestos por `(status, queued_at)` si aumenta carga.
#
# Riesgos en producción:
# - Cálculo de posición de cola es sensible a concurrencia y snapshot transaccional.
#
# Escalabilidad:
# - I/O-bound, con hotspots en tablas `simulation_job` y `simulation_job_event`.
