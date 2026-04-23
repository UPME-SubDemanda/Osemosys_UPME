"""Tabla de unión M:M entre escenarios y etiquetas."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ScenarioTagLink(Base):
    """Asociación de una etiqueta a un escenario."""

    __tablename__ = "scenario_tag_link"
    __table_args__ = ({"schema": "osemosys"},)

    scenario_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("osemosys.scenario.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("osemosys.scenario_tag.id", ondelete="CASCADE"),
        primary_key=True,
    )
