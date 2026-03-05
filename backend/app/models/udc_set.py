"""Modelo ORM para conjunto `UdcSet`."""

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UdcSet(Base):
    """Catálogo para restricciones definidas por usuario (UDC)."""

    __tablename__ = "udc_set"
    __table_args__ = (
        UniqueConstraint("code", name="udc_set_code"),
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
# - Proveer identificadores para constraints personalizadas.
#
# Posibles mejoras:
# - Añadir campos de expresión/metadata para trazabilidad de UDC.
#
# Riesgos en producción:
# - Nombres ambiguos dificultan auditoría de restricciones.
#
# Escalabilidad:
# - Catálogo pequeño.
