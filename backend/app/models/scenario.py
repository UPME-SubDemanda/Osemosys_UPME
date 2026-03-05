"""Modelo ORM de escenarios de análisis OSEMOSYS."""

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


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
        {"schema": "osemosys"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    edit_policy: Mapped[str] = mapped_column(String(20), nullable=False, default="OWNER_ONLY")
    is_template: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    udc_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)


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
