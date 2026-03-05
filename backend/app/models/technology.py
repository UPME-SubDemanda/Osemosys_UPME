"""Modelo ORM para catálogo `Technology`."""

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Technology(Base):
    """Catálogo de tecnologías del sistema."""

    __tablename__ = "technology"
    __table_args__ = (
        UniqueConstraint("name", name="technology_name"),
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
# - Definir tecnologías empleadas por parámetros y restricciones.
#
# Posibles mejoras:
# - Añadir clasificación tecnológica (renovable, térmica, almacenamiento).
#
# Riesgos en producción:
# - Altas/bajas no gobernadas afectan consistencia de escenarios.
#
# Escalabilidad:
# - Baja a media cardinalidad.
