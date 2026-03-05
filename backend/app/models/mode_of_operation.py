"""Modelo ORM para conjunto `ModeOfOperation`."""

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModeOfOperation(Base):
    """Catálogo de modos de operación tecnológicos."""

    __tablename__ = "mode_of_operation"
    __table_args__ = (
        UniqueConstraint("code", name="mode_of_operation_code"),
        {"schema": "osemosys"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Identificar modos operativos para modelación de flujos/costos.
#
# Posibles mejoras:
# - Añadir metadata para reglas de validación de combinaciones.
#
# Riesgos en producción:
# - Reuso ambiguo de códigos entre tecnologías.
#
# Escalabilidad:
# - Catálogo de baja cardinalidad.
