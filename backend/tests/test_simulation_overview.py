from __future__ import annotations

from datetime import datetime, timedelta, timezone

import app.services.simulation_service as simulation_service_module
from app.models import SimulationJob, SimulationJobEvent
from app.services.simulation_service import SimulationService

from factories import create_scenario, create_user


def test_global_simulation_list_and_overview(db_session, monkeypatch) -> None:
    owner = create_user(db_session, username="sim-owner")
    other = create_user(db_session, username="sim-other")
    scenario_a = create_scenario(db_session, name="Scenario A", owner=owner.username, edit_policy="OPEN")
    scenario_b = create_scenario(db_session, name="Scenario B", owner=other.username, edit_policy="OPEN")

    now = datetime.now(timezone.utc)
    job_queued_1 = SimulationJob(
        user_id=owner.id,
        scenario_id=scenario_a.id,
        solver_name="highs",
        status="QUEUED",
        progress=0.0,
        queued_at=now - timedelta(minutes=5),
    )
    job_queued_2 = SimulationJob(
        user_id=other.id,
        scenario_id=scenario_b.id,
        solver_name="glpk",
        status="QUEUED",
        progress=0.0,
        queued_at=now - timedelta(minutes=1),
    )
    job_running = SimulationJob(
        user_id=other.id,
        scenario_id=scenario_a.id,
        solver_name="highs",
        status="RUNNING",
        progress=42.0,
        queued_at=now - timedelta(minutes=2),
        started_at=now - timedelta(minutes=1),
    )
    db_session.add_all([job_queued_1, job_queued_2, job_running])
    db_session.commit()
    for job in (job_queued_1, job_queued_2, job_running):
        db_session.refresh(job)

    db_session.add(
        SimulationJobEvent(
            job_id=job_running.id,
            event_type="INFO",
            stage="runner",
            message="Running",
            progress=42.0,
        )
    )
    db_session.commit()

    monkeypatch.setattr(
        simulation_service_module.DockerMetricsService,
        "list_service_memory",
        staticmethod(
            lambda: [
                {"service_name": "api", "memory_usage_bytes": 100},
                {"service_name": "simulation-worker", "memory_usage_bytes": 250},
            ]
        ),
    )

    listed = SimulationService.list_jobs(
        db_session,
        current_user=owner,
        scope="global",
        status=None,
        username=None,
        scenario_id=None,
        solver_name=None,
        cantidad=50,
        offset=1,
    )
    assert listed["meta"].total == 3
    queued_positions = {
        row["id"]: row["queue_position"]
        for row in listed["data"]
        if row["status"] == "QUEUED"
    }
    assert queued_positions[job_queued_1.id] == 1
    assert queued_positions[job_queued_2.id] == 2
    usernames = {row["username"] for row in listed["data"]}
    scenario_names = {row["scenario_name"] for row in listed["data"]}
    assert usernames == {owner.username, other.username}
    assert scenario_names == {"Scenario A", "Scenario B"}

    logs = SimulationService.list_logs(
        db_session,
        current_user=owner,
        job_id=job_running.id,
        cantidad=20,
        offset=1,
    )
    assert logs["meta"].total == 1
    assert logs["data"][0]["message"] == "Running"

    overview = SimulationService.overview(db_session, current_user=owner)
    assert overview["queued_count"] == 2
    assert overview["running_count"] == 1
    assert overview["active_count"] == 3
    assert overview["total_count"] == 3
    assert overview["services_memory_total_bytes"] == 350
