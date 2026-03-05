from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

import app.simulation.tasks as tasks_module


@dataclass
class DummyResult:
    rowcount: int


class DummyDbSession:
    def __init__(self, rowcount: int) -> None:
        self._rowcount = rowcount
        self.commit_calls = 0

    def execute(self, _stmt: object) -> DummyResult:
        return DummyResult(rowcount=self._rowcount)

    def commit(self) -> None:
        self.commit_calls += 1


class DummySessionFactory:
    def __init__(self, db: DummyDbSession) -> None:
        self._db = db

    def __call__(self):
        db = self._db

        class _Ctx:
            def __enter__(self_inner) -> DummyDbSession:
                return db

            def __exit__(self_inner, exc_type, exc, tb) -> bool:
                return False

        return _Ctx()


@pytest.mark.parametrize("status", ["RUNNING", "FAILED", "CANCELLED", "SUCCEEDED"])
def test_run_simulation_job_is_noop_for_non_queued_status(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    db = DummyDbSession(rowcount=0)
    job = SimpleNamespace(status=status)

    monkeypatch.setattr(tasks_module, "SessionLocal", DummySessionFactory(db))
    monkeypatch.setattr(
        tasks_module.SimulationRepository,
        "get_job_by_id",
        lambda _db, *, job_id: job,
    )
    monkeypatch.setattr(
        tasks_module.SimulationRepository,
        "add_event",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("No event expected")),
    )
    monkeypatch.setattr(
        tasks_module,
        "run_pipeline",
        lambda _db, *, job_id: (_ for _ in ()).throw(AssertionError("Pipeline should not run")),
    )

    tasks_module.run_simulation_job.run(123)

    assert db.commit_calls == 1
