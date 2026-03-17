"""Repositorio para jobs asíncronos de operaciones de escenario."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, aliased

from app.models import ScenarioOperationJob, ScenarioOperationJobEvent, Scenario, User


class ScenarioOperationRepository:
    """Acceso a datos de operaciones largas de escenarios."""

    @staticmethod
    def create_job(
        db: Session,
        *,
        operation_type: str,
        user_id: uuid.UUID,
        scenario_id: int | None,
        payload_json: dict | None,
    ) -> ScenarioOperationJob:
        job = ScenarioOperationJob(
            operation_type=operation_type,
            status="QUEUED",
            user_id=user_id,
            scenario_id=scenario_id,
            progress=0.0,
            stage="queue",
            message="Operación encolada.",
            payload_json=payload_json or None,
        )
        db.add(job)
        return job

    @staticmethod
    def get_by_id(db: Session, *, job_id: int) -> ScenarioOperationJob | None:
        return db.get(ScenarioOperationJob, job_id)

    @staticmethod
    def get_visible(
        db: Session, *, job_id: int
    ) -> tuple[ScenarioOperationJob, str | None, str | None, str | None] | None:
        target_scenario = aliased(Scenario)
        stmt = (
            select(
                ScenarioOperationJob,
                User.username.label("username"),
                Scenario.name.label("scenario_name"),
                target_scenario.name.label("target_scenario_name"),
            )
            .join(User, User.id == ScenarioOperationJob.user_id)
            .outerjoin(Scenario, Scenario.id == ScenarioOperationJob.scenario_id)
            .outerjoin(target_scenario, target_scenario.id == ScenarioOperationJob.target_scenario_id)
            .where(ScenarioOperationJob.id == job_id)
        )
        row = db.execute(stmt).one_or_none()
        if row is None:
            return None
        return row[0], row.username, row.scenario_name, row.target_scenario_name

    @staticmethod
    def list_jobs(
        db: Session,
        *,
        user_id: uuid.UUID,
        status: str | None,
        operation_type: str | None,
        scenario_id: int | None,
        row_offset: int,
        limit: int,
    ) -> tuple[list[tuple[ScenarioOperationJob, str | None, str | None, str | None]], int]:
        target_scenario = aliased(Scenario)
        stmt = (
            select(
                ScenarioOperationJob,
                User.username.label("username"),
                Scenario.name.label("scenario_name"),
                target_scenario.name.label("target_scenario_name"),
            )
            .join(User, User.id == ScenarioOperationJob.user_id)
            .outerjoin(Scenario, Scenario.id == ScenarioOperationJob.scenario_id)
            .outerjoin(target_scenario, target_scenario.id == ScenarioOperationJob.target_scenario_id)
        )
        filters = [ScenarioOperationJob.user_id == user_id]
        if status:
            filters.append(ScenarioOperationJob.status == status)
        if operation_type:
            filters.append(ScenarioOperationJob.operation_type == operation_type)
        if scenario_id is not None:
            filters.append(ScenarioOperationJob.scenario_id == scenario_id)

        stmt = stmt.where(and_(*filters))
        count_stmt = select(func.count()).select_from(ScenarioOperationJob).where(and_(*filters))
        total = int(db.scalar(count_stmt) or 0)
        rows = (
            db.execute(
                stmt.order_by(ScenarioOperationJob.queued_at.desc(), ScenarioOperationJob.id.desc())
                .offset(row_offset)
                .limit(limit)
            )
            .all()
        )
        return [(r[0], r.username, r.scenario_name, r.target_scenario_name) for r in rows], total

    @staticmethod
    def add_event(
        db: Session,
        *,
        job_id: int,
        event_type: str,
        stage: str | None,
        message: str | None,
        progress: float | None,
    ) -> ScenarioOperationJobEvent:
        event = ScenarioOperationJobEvent(
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
    ) -> tuple[list[ScenarioOperationJobEvent], int]:
        total = int(
            db.scalar(
                select(func.count())
                .select_from(ScenarioOperationJobEvent)
                .where(ScenarioOperationJobEvent.job_id == job_id)
            )
            or 0
        )
        items = (
            db.execute(
                select(ScenarioOperationJobEvent)
                .where(ScenarioOperationJobEvent.job_id == job_id)
                .order_by(ScenarioOperationJobEvent.created_at.asc())
                .offset(row_offset)
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return list(items), total
