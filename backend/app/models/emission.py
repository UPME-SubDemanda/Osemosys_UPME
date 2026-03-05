"""Modelo ORM para catálogo `Emission`."""

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Emission(Base):
    """Catálogo de emisiones (CO2, CH4, etc.)."""

    __tablename__ = "emission"
    __table_args__ = (
        UniqueConstraint("name", name="emission_name"),
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
# - Identificar contaminantes usados por constraints e indicadores.
#
# Posibles mejoras:
# - Añadir factor de equivalencia CO2e por emisión.
#
# Riesgos en producción:
# - Cambios de naming pueden desalinear reporting histórico.
#
# Escalabilidad:
# - Baja cardinalidad.
