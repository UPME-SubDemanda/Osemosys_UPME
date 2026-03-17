"""Modelo ORM para jobs de simulacion en cola/ejecucion."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SimulationJob(Base):
    """Estado principal de cada corrida OSEMOSYS solicitada por usuario."""

    __tablename__ = "simulation_job"
    __table_args__ = (
        CheckConstraint(
            "status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED')",
            name="simulation_job_status",
        ),
        Index("ix_simulation_job_user_status", "user_id", "status"),
        Index("ix_simulation_job_scenario", "scenario_id"),
        {"schema": "osemosys"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[object] = mapped_column(
        Uuid, ForeignKey("core.user.id", ondelete="RESTRICT"), nullable=False
    )
    scenario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("osemosys.scenario.id", ondelete="RESTRICT"), nullable=False
    )
    solver_name: Mapped[str] = mapped_column(String(20), nullable=False, default="highs")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="QUEUED")
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    queued_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Result summary (populated when job succeeds) ---
    objective_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    coverage_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_demand: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_dispatch: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_unmet: Mapped[float | None] = mapped_column(Float, nullable=True)
    records_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    osemosys_param_records: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stage_times_json: Mapped[object | None] = mapped_column(JSON, nullable=True)
    model_timings_json: Mapped[object | None] = mapped_column(JSON, nullable=True)
    inputs_summary_json: Mapped[object | None] = mapped_column(JSON, nullable=True)
