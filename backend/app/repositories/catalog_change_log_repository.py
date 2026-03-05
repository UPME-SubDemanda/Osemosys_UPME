"""Repositorio para auditoría de catálogos."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import CatalogChangeLog


class CatalogChangeLogRepository:
    """Inserciones de trazabilidad para operaciones sobre catálogos."""

    @staticmethod
    def create(
        db: Session,
        *,
        entity_type: str,
        entity_id: int,
        action: str,
        old_name: str | None,
        new_name: str | None,
        justification: str | None,
        changed_by: str,
    ) -> CatalogChangeLog:
        """Registra evento de auditoría para alta/edición/desactivación."""
        obj = CatalogChangeLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            old_name=old_name,
            new_name=new_name,
            justification=justification,
            changed_by=changed_by,
        )
        db.add(obj)
        return obj


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Persistir rastro de cambios de catálogos.
#
# Posibles mejoras:
# - Incorporar campos de contexto (request_id, origen, ip/actor técnico).
#
# Riesgos en producción:
# - Si no se consulta periódicamente, el histórico crecerá sin particionamiento.
#
# Escalabilidad:
# - Escritura I/O-bound de bajo costo por evento.
