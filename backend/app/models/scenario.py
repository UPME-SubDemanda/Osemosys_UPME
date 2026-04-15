"""Modelo ORM de escenarios de análisis OSEMOSYS."""

from __future__ import annotations

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.scenario_tag import ScenarioTag


class Scenario(Base):
    """Escenario de trabajo (schema `osemosys`).

    `edit_policy` restringe quién puede modificar: OWNER_ONLY | OPEN | RESTRICTED.
    """

    __tablename__ = "scenario"
    __table_args__ = (
        CheckConstraint(
            "edit_policy IN ('OWNER_ONLY','OPEN','RESTRICTED')",
            name="scenario_edit_policy",
        ),
        Index("ix_scenario_base_scenario_id", "base_scenario_id"),
        Index("ix_scenario_tag_id", "tag_id"),
        {"schema": "osemosys"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    base_scenario_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("osemosys.scenario.id", ondelete="RESTRICT"),
        nullable=True,
    )
    changed_param_names: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, default=None)
    edit_policy: Mapped[str] = mapped_column(String(20), nullable=False, default="OWNER_ONLY")
    is_template: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    udc_config: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    tag_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("osemosys.scenario_tag.id", ondelete="SET NULL"),
        nullable=True,
    )
    tag_row: Mapped[ScenarioTag | None] = relationship("ScenarioTag", back_populates="scenarios")


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Persistir escenarios, owner y política de edición.
#
# Posibles mejoras:
# - Validar policy con enum de Python para robustez de tipado.
#
# Riesgos en producción:
# - Cambio de policy sin auditoría puede alterar gobernanza de cambios.
#
# Escalabilidad:
# - I/O-bound, cardinalidad media.
