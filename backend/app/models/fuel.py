"""Modelo ORM para catálogo `Fuel`."""

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Fuel(Base):
    """Catálogo de combustibles."""

    __tablename__ = "fuel"
    __table_args__ = (
        UniqueConstraint("name", name="fuel_name"),
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
# - Representar fuentes energéticas consumibles del modelo.
#
# Posibles mejoras:
# - Agregar propiedades fisicoquímicas/energéticas para validaciones.
#
# Riesgos en producción:
# - Cambios semánticos del catálogo sin versionado pueden sesgar resultados.
#
# Escalabilidad:
# - Baja cardinalidad.
