"""Modelo ORM para conjunto `Timeslice` de OSEMOSYS."""

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Timeslice(Base):
    """Catálogo de segmentos temporales intra-anuales."""

    __tablename__ = "timeslice"
    __table_args__ = (
        UniqueConstraint("code", name="timeslice_code"),
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
# - Definir particiones temporales utilizadas por parámetros/constraints.
#
# Posibles mejoras:
# - Validar compatibilidad contra season/daytype/dailytimebracket.
#
# Riesgos en producción:
# - Códigos inconsistentes afectan indexación de parámetros multidimensionales.
#
# Escalabilidad:
# - Catálogo pequeño y estable.
