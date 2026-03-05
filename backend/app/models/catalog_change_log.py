"""Modelo ORM para auditoría de cambios en catálogos."""

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CatalogChangeLog(Base):
    """Bitácora de cambios CRUD lógicos sobre catálogos."""

    __tablename__ = "catalog_change_log"
    __table_args__ = {"schema": "osemosys"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    old_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Trazabilidad funcional para gobernanza de catálogos.
#
# Posibles mejoras:
# - Agregar `request_id` y `actor_id` para trazabilidad operacional completa.
#
# Riesgos en producción:
# - Sin retención/particionado puede crecer significativamente.
#
# Escalabilidad:
# - Escritura frecuente, lectura eventual; indexar por `entity_type` si aumenta uso.
