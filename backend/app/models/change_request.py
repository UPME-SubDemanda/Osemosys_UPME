"""Modelo ORM para solicitud de cambio de `OsemosysParamValue`."""

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChangeRequest(Base):
    """Cabecera de workflow de aprobación/rechazo de cambios."""

    __tablename__ = "change_request"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED')",
            name="change_request_status",
        ),
        Index("ix_change_request_id_osemosys_param_value", "id_osemosys_param_value"),
        Index("ix_change_request_status", "status"),
        {"schema": "osemosys"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_osemosys_param_value: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("osemosys.osemosys_param_value.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Persistir estado de aprobación de cambios sobre inputs del modelo.
#
# Posibles mejoras:
# - Agregar campos `reviewed_by`, `reviewed_at`, `comment`.
#
# Riesgos en producción:
# - Estados limitados pueden ser insuficientes para flujos regulatorios complejos.
#
# Escalabilidad:
# - Tabla de historial con crecimiento continuo; considerar archivado.

