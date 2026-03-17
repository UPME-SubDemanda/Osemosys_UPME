"""Bitácora de eventos para operaciones asíncronas de escenarios."""

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ScenarioOperationJobEvent(Base):
    """Eventos cronológicos de `ScenarioOperationJob`."""

    __tablename__ = "scenario_operation_job_event"
    __table_args__ = (
        Index("ix_scenario_operation_event_job_id", "job_id"),
        Index("ix_scenario_operation_event_job_created", "job_id", "created_at"),
        {"schema": "osemosys"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("osemosys.scenario_operation_job.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(20), nullable=False, default="INFO")
    stage: Mapped[str | None] = mapped_column(String(80), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
