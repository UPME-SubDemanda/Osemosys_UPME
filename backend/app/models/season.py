"""Modelo ORM para conjunto `Season`."""

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Season(Base):
    """Catálogo estacional para desagregación temporal."""

    __tablename__ = "season"
    __table_args__ = (
        UniqueConstraint("code", name="season_code"),
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
# - Definir estaciones para constraints y series del modelo.
#
# Posibles mejoras:
# - Adjuntar orden cronológico explícito.
#
# Riesgos en producción:
# - Convenciones de códigos no homogéneas entre datasets.
#
# Escalabilidad:
# - Catálogo pequeño.
