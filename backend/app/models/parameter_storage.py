"""Modelo ORM para atributos de almacenamiento ligados a `ParameterValue`."""

from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ParameterStorage(Base):
    """Extensión de dimensión temporal para casos de storage."""

    __tablename__ = "parameter_storage"
    __table_args__ = (
        UniqueConstraint("id_parameter_value", name="parameter_storage_id_parameter_value"),
        Index("ix_parameter_storage_id_parameter_value", "id_parameter_value"),
        {"schema": "osemosys"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_parameter_value: Mapped[int] = mapped_column(
        Integer, ForeignKey("osemosys.parameter_value.id", ondelete="RESTRICT"), nullable=False
    )

    timesline: Mapped[int | None] = mapped_column(Integer, nullable=True)
    daytype: Mapped[int | None] = mapped_column(Integer, nullable=True)
    season: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dailytimebracket: Mapped[int | None] = mapped_column(Integer, nullable=True)
    id_storage_set: Mapped[int | None] = mapped_column(Integer, nullable=True)


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Guardar desagregaciones específicas para modelación de almacenamiento.
#
# Posibles mejoras:
# - Corregir naming `timesline` -> `timeslice` en una migración controlada.
#
# Riesgos en producción:
# - Inconsistencia de naming puede inducir errores de interpretación.
#
# Escalabilidad:
# - Volumen acotado por relación 1:1 con `parameter_value`.

