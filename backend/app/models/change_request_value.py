"""Modelo ORM con detalle de valores en una solicitud de cambio."""

from sqlalchemy import Float, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChangeRequestValue(Base):
    """Snapshot de valor anterior y valor propuesto."""

    __tablename__ = "change_request_value"
    __table_args__ = (
        Index("ix_change_request_value_id_change_request", "id_change_request"),
        {"schema": "osemosys"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_change_request: Mapped[int] = mapped_column(
        Integer, ForeignKey("osemosys.change_request.id", ondelete="RESTRICT"), nullable=False
    )
    old_value: Mapped[float] = mapped_column(Float, nullable=False)
    new_value: Mapped[float] = mapped_column(Float, nullable=False)


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Registrar delta numérico asociado a cada `ChangeRequest`.
#
# Posibles mejoras:
# - Incluir unidad y metadatos de contexto del cambio.
#
# Riesgos en producción:
# - Si se permite múltiple detalle por request, debe definirse semántica explícita.
#
# Escalabilidad:
# - Bajo costo por fila, crecimiento proporcional a historial.

