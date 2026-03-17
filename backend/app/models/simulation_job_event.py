"""Modelo ORM para eventos de progreso/log de simulación."""

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SimulationJobEvent(Base):
    """Bitácora cronológica asociada a `SimulationJob`."""

    __tablename__ = "simulation_job_event"
    __table_args__ = (
        Index("ix_simulation_job_event_job_id", "job_id"),
        Index("ix_simulation_job_event_job_created_at", "job_id", "created_at"),
        {"schema": "osemosys"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("osemosys.simulation_job.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(20), nullable=False, default="INFO")
    stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Registrar etapas, mensajes y progreso para observabilidad de corridas.
#
# Posibles mejoras:
# - Añadir severidad estructurada y código de evento.
#
# Riesgos en producción:
# - Altísimo volumen si se loguea demasiado granular.
#
# Escalabilidad:
# - Crecimiento rápido; requerirá estrategia de retención.
