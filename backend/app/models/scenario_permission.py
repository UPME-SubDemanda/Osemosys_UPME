"""Modelo ORM para permisos de usuarios por escenario."""

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ScenarioPermission(Base):
    """Matriz de permisos por escenario y usuario."""

    __tablename__ = "scenario_permission"
    __table_args__ = (
        UniqueConstraint("id_scenario", "user_identifier", name="scenario_permission_scenario_user"),
        Index("ix_scenario_permission_id_scenario", "id_scenario"),
        Index("ix_scenario_permission_user_identifier", "user_identifier"),
        Index("ix_scenario_permission_user_id", "user_id"),
        {"schema": "osemosys"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_scenario: Mapped[int] = mapped_column(
        Integer, ForeignKey("osemosys.scenario.id", ondelete="RESTRICT"), nullable=False
    )
    user_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[object | None] = mapped_column(
        Uuid, ForeignKey("core.user.id", ondelete="RESTRICT"), nullable=True
    )
    can_edit_direct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_propose: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_manage_values: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Controlar capacidades de edición/propuesta/gestión por escenario.
#
# Posibles mejoras:
# - Reemplazar flags por modelo RBAC explícito.
#
# Riesgos en producción:
# - Combinaciones de flags ambiguas pueden generar políticas difíciles de auditar.
#
# Escalabilidad:
# - I/O-bound; índice por `user_id` crítico para consultas frecuentes.

