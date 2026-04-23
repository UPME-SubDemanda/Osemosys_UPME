"""Categoría jerárquica para agrupar etiquetas de escenario."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.scenario_tag import ScenarioTag


class ScenarioTagCategory(Base):
    """Agrupa etiquetas por jerarquía y define reglas de asignación.

    - `hierarchy_level`: 1 es el nivel más alto (ej. estado: oficial/trabajando),
      2 el siguiente (ej. tipo de escenario: PA/Referencia), etc.
    - `max_tags_per_scenario`: si es 1 → un escenario solo puede tener una etiqueta
      de esta categoría (reasignar quita la anterior). None → ilimitado.
    - `is_exclusive_combination`: si True, la combinación de una etiqueta de esta
      categoría con las de otras categorías debe ser única entre escenarios
      (ej. solo puede haber un "Oficial+PA" en el sistema).
    """

    __tablename__ = "scenario_tag_category"
    __table_args__ = (
        UniqueConstraint("name", name="uq_scenario_tag_category_name"),
        Index("ix_scenario_tag_category_hierarchy", "hierarchy_level", "sort_order"),
        {"schema": "osemosys"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    hierarchy_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_tags_per_scenario: Mapped[int | None] = mapped_column(Integer, nullable=True, default=1)
    is_exclusive_combination: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#64748B")

    tags: Mapped[list["ScenarioTag"]] = relationship(
        "ScenarioTag",
        back_populates="category",
        cascade="all, delete-orphan",
    )
