"""Etiquetas globales para priorizar y colorear escenarios en listados."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.scenario import Scenario


class ScenarioTag(Base):
    """Catálogo de etiquetas (nombre, color, orden de prioridad)."""

    __tablename__ = "scenario_tag"
    __table_args__ = (
        UniqueConstraint("name", name="uq_scenario_tag_name"),
        Index("ix_scenario_tag_sort_order", "sort_order"),
        {"schema": "osemosys"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    scenarios: Mapped[list[Scenario]] = relationship(
        "Scenario",
        back_populates="tag_row",
    )
