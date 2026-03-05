"""Modelo ORM para catálogo `Parameter`."""

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Parameter(Base):
    """Catálogo de parámetros base del modelo energético."""

    __tablename__ = "parameter"
    __table_args__ = (
        UniqueConstraint("name", name="parameter_name"),
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
# - Definir parámetros configurables del dominio OSEMOSYS.
#
# Posibles mejoras:
# - Añadir metadata (grupo, unidad sugerida, descripción técnica).
#
# Riesgos en producción:
# - Renombres de parámetros impactan loaders/mapeos de simulación.
#
# Escalabilidad:
# - Catálogo compacto; bajo costo.
