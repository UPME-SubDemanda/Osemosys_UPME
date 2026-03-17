"""Tareas Celery para operaciones asíncronas de escenarios."""

from __future__ import annotations

from app.db.session import SessionLocal
from app.services.scenario_operation_service import ScenarioOperationService
from app.simulation.celery_app import celery_app


@celery_app.task(name="app.scenario.tasks.run_scenario_operation_job", bind=True)
def run_scenario_operation_job(self, job_id: int) -> None:
    with SessionLocal() as db:
        ScenarioOperationService.execute_job(db, job_id=job_id)
