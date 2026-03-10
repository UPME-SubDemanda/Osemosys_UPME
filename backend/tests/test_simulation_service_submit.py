from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest

from app.core.exceptions import ConflictError
import app.services.simulation_service as simulation_service_module
from app.services.simulation_service import SimulationService


class DummyDbSession:
    def __init__(self) -> None:
        self.commit_calls = 0
        self.refresh_calls = 0
        self.rollback_calls = 0
        self.flush_calls = 0

    def commit(self) -> None:
        self.commit_calls += 1

    def flush(self) -> None:
        self.flush_calls += 1

    def refresh(self, _obj: object) -> None:
        self.refresh_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1


def _build_job(user_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=123,
        scenario_id=1,
        user_id=user_id,
        solver_name="highs",
        status="QUEUED",
        progress=0.0,
        cancel_requested=False,
        queue_position=None,
        result_ref=None,
        error_message=None,
        queued_at=datetime.now(timezone.utc),
        started_at=None,
        finished_at=None,
        celery_task_id=None,
    )


def test_submit_persists_task_id_after_enqueue(monkeypatch: pytest.MonkeyPatch) -> None:
    current_user = SimpleNamespace(id=uuid.uuid4(), username="seed")
    scenario = SimpleNamespace(id=1, owner="seed", name="Escenario seed")
    job = _build_job(current_user.id)
    db = DummyDbSession()
    events: list[dict] = []

    monkeypatch.setattr(
        simulation_service_module,
        "get_settings",
        lambda: SimpleNamespace(sim_user_active_limit=4, simulation_mode="async"),
    )
    from app.services.scenario_service import ScenarioService

    monkeypatch.setattr(
        ScenarioService,
        "_require_access",
        staticmethod(lambda _db, *, scenario_id, current_user: scenario),
    )
    monkeypatch.setattr(
        simulation_service_module.SimulationRepository,
        "count_user_active_jobs",
        lambda _db, *, user_id: 0,
    )
    monkeypatch.setattr(
        simulation_service_module.SimulationRepository,
        "create_job",
        lambda _db, *, user_id, scenario_id, solver_name: job,
    )
    monkeypatch.setattr(
        simulation_service_module.SimulationRepository,
        "add_event",
        lambda _db, *, job_id, event_type, stage, message, progress: events.append(
            {
                "job_id": job_id,
                "event_type": event_type,
                "stage": stage,
                "message": message,
                "progress": progress,
            }
        ),
    )
    monkeypatch.setattr(
        simulation_service_module.SimulationRepository,
        "queue_position",
        lambda _db, *, job_id: 1,
    )

    class _TaskStub:
        @staticmethod
        def delay(job_id: int) -> SimpleNamespace:
            assert job_id == job.id
            return SimpleNamespace(id="task-123")

    monkeypatch.setattr(simulation_service_module, "run_simulation_job", _TaskStub())

    payload = SimulationService.submit(
        db,
        current_user=current_user,
        scenario_id=1,
        solver_name="highs",
    )

    assert payload["id"] == job.id
    assert payload["queue_position"] == 1
    assert job.celery_task_id == "task-123"
    assert db.flush_calls == 1
    assert db.commit_calls == 2
    assert len(events) == 2
    assert events[0]["message"] == "Job creado y listo para encolar."
    assert events[1]["message"] == "Simulacion encolada."


def test_submit_marks_job_failed_when_enqueue_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    current_user = SimpleNamespace(id=uuid.uuid4(), username="seed")
    scenario = SimpleNamespace(id=1, owner="seed", name="Escenario seed")
    job = _build_job(current_user.id)
    db = DummyDbSession()
    events: list[dict] = []

    monkeypatch.setattr(
        simulation_service_module,
        "get_settings",
        lambda: SimpleNamespace(sim_user_active_limit=4, simulation_mode="async"),
    )
    from app.services.scenario_service import ScenarioService

    monkeypatch.setattr(
        ScenarioService,
        "_require_access",
        staticmethod(lambda _db, *, scenario_id, current_user: scenario),
    )
    monkeypatch.setattr(
        simulation_service_module.SimulationRepository,
        "count_user_active_jobs",
        lambda _db, *, user_id: 0,
    )
    monkeypatch.setattr(
        simulation_service_module.SimulationRepository,
        "create_job",
        lambda _db, *, user_id, scenario_id, solver_name: job,
    )
    monkeypatch.setattr(
        simulation_service_module.SimulationRepository,
        "get_job_by_id",
        lambda _db, *, job_id: job,
    )
    monkeypatch.setattr(
        simulation_service_module.SimulationRepository,
        "add_event",
        lambda _db, *, job_id, event_type, stage, message, progress: events.append(
            {
                "job_id": job_id,
                "event_type": event_type,
                "stage": stage,
                "message": message,
                "progress": progress,
            }
        ),
    )

    class _TaskStub:
        @staticmethod
        def delay(_job_id: int) -> SimpleNamespace:
            raise RuntimeError("broker down")

    monkeypatch.setattr(simulation_service_module, "run_simulation_job", _TaskStub())

    with pytest.raises(ConflictError):
        SimulationService.submit(
            db,
            current_user=current_user,
            scenario_id=1,
            solver_name="highs",
        )

    assert db.flush_calls == 1
    assert db.commit_calls == 2
    assert db.rollback_calls == 1
    assert job.status == "FAILED"
    assert "QUEUE_ENQUEUE_ERROR" in (job.error_message or "")
    assert any(e["event_type"] == "ERROR" and e["stage"] == "queue" for e in events)
