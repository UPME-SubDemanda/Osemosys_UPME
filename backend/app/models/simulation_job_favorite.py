"""Favoritos de resultados de simulación por usuario."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SimulationJobFavorite(Base):
    """Marca un job de simulación como favorito del usuario (per-user)."""

    __tablename__ = "simulation_job_favorite"
    __table_args__ = (
        Index("ix_simulation_job_favorite_job_id", "job_id"),
        {"schema": "osemosys"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("core.user.id", ondelete="CASCADE"),
        primary_key=True,
    )
    job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("osemosys.simulation_job.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
