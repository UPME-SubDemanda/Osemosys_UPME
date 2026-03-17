"""Modelo ORM para catálogo `Region`."""

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Region(Base):
    """Catálogo de regiones energéticas."""

    __tablename__ = "region"
    __table_args__ = (
        UniqueConstraint("name", name="region_name"),
        {"schema": "osemosys"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Representar ámbito geográfico para parámetros y resultados.
#
# Posibles mejoras:
# - Soporte de jerarquías (país/zona/subzona).
#
# Riesgos en producción:
# - Reasignaciones regionales pueden romper comparabilidad temporal.
#
# Escalabilidad:
# - Baja cardinalidad esperada.
