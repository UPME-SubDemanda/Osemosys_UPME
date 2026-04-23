"""Etiquetas globales para marcar escenarios; pertenecen a una categoría jerárquica."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.scenario import Scenario
    from app.models.scenario_tag_category import ScenarioTagCategory


class ScenarioTag(Base):
    """Etiqueta asignable a escenarios, siempre ligada a una categoría."""

    __tablename__ = "scenario_tag"
    __table_args__ = (
        UniqueConstraint("category_id", "name", name="uq_scenario_tag_category_tag_name"),
        Index("ix_scenario_tag_sort_order", "sort_order"),
        Index("ix_scenario_tag_category_id", "category_id"),
        {"schema": "osemosys"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("osemosys.scenario_tag_category.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Si True, la combinación de este tag con los tags asignados al escenario de
    # otras categorías debe ser única entre todos los escenarios del sistema.
    # Independiente del flag de la categoría; se puede marcar solo para
    # etiquetas específicas (p.ej. "Oficial") sin afectar a hermanos.
    is_exclusive_combination: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    category: Mapped["ScenarioTagCategory"] = relationship(
        "ScenarioTagCategory",
        back_populates="tags",
    )
    scenarios: Mapped[list["Scenario"]] = relationship(
        "Scenario",
        secondary="osemosys.scenario_tag_link",
        back_populates="tags",
    )
