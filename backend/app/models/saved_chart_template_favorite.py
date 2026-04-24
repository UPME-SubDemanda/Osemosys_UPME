"""Favoritos de plantillas de gráfica, por usuario."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SavedChartTemplateFavorite(Base):
    """Marca una ``saved_chart_template`` como favorita del usuario."""

    __tablename__ = "saved_chart_template_favorite"
    __table_args__ = (
        Index(
            "ix_saved_chart_template_favorite_template_id",
            "template_id",
        ),
        {"schema": "osemosys"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("core.user.id", ondelete="CASCADE"),
        primary_key=True,
    )
    template_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "osemosys.saved_chart_template.id", ondelete="CASCADE"
        ),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
