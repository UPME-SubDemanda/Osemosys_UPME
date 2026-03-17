"""Servicio de negocio para catálogo `Region`."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models import OsemosysParamValue, ParameterValue, User
from app.repositories.catalog_change_log_repository import CatalogChangeLogRepository
from app.repositories.region_repository import RegionRepository
from app.services.pagination import build_meta, normalize_pagination


class RegionService:
    """Operaciones de negocio para regiones energéticas."""

    @staticmethod
    @staticmethod
    def _is_used(db: Session, *, region_id: int) -> bool:
        in_parameter_value = (
            db.query(ParameterValue.id).filter(ParameterValue.id_region == region_id).limit(1).first() is not None
        )
        in_osemosys_value = (
            db.query(OsemosysParamValue.id).filter(OsemosysParamValue.id_region == region_id).limit(1).first()
            is not None
        )
        return in_parameter_value or in_osemosys_value

    @staticmethod
    def _require_justification_if_used(
        db: Session, *, region_id: int, justification: str | None
    ) -> str | None:
        clean = (justification or "").strip() or None
        if RegionService._is_used(db, region_id=region_id) and not clean:
            raise ConflictError(
                "Esta región ya está utilizada en escenarios. Debes enviar una justificación."
            )
        return clean

    @staticmethod
    def list(
        db: Session,
        *,
        busqueda: str | None,
        is_active: bool | None,
        cantidad: int | None,
        offset: int | None,
    ) -> dict:
        """Lista regiones con filtros de texto y estado lógico."""
        page, page_size, row_offset = normalize_pagination(offset, cantidad)
        items, total = RegionRepository.get_paginated(
            db,
            busqueda=busqueda,
            is_active=is_active,
            row_offset=row_offset,
            limit=page_size,
        )
        meta = build_meta(page, page_size, total, busqueda)
        return {"data": items, "meta": meta}

    @staticmethod
    def list_inactive(
        db: Session,
        *,
        busqueda: str | None,
        cantidad: int | None,
        offset: int | None,
    ) -> dict:
        """Lista únicamente regiones desactivadas."""
        return RegionService.list(
            db,
            busqueda=busqueda,
            is_active=False,
            cantidad=cantidad,
            offset=offset,
        )

    @staticmethod
    def create(db: Session, *, name: str, current_user: User):
        """Crea región y persiste auditoría de creación."""
        obj = RegionRepository.create(db, name=name)
        try:
            db.flush()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("Ya existe un registro con ese nombre.") from e
        CatalogChangeLogRepository.create(
            db,
            entity_type="region",
            entity_id=obj.id,
            action="CREATE",
            old_name=None,
            new_name=obj.name,
            justification=None,
            changed_by=current_user.username,
        )
        db.commit()
        db.refresh(obj)
        return obj

    @staticmethod
    def update(
        db: Session,
        *,
        region_id: int,
        name: str,
        current_user: User,
        justification: str | None = None,
    ):
        """Actualiza nombre de región con control de colisiones."""
        obj = RegionRepository.get_by_id(db, region_id)
        if not obj:
            raise NotFoundError("No encontrado.")
        old_name = obj.name
        clean_justification = RegionService._require_justification_if_used(
            db, region_id=obj.id, justification=justification
        )
        obj.name = name
        try:
            db.flush()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("Ya existe un registro con ese nombre.") from e
        CatalogChangeLogRepository.create(
            db,
            entity_type="region",
            entity_id=obj.id,
            action="UPDATE",
            old_name=old_name,
            new_name=obj.name,
            justification=clean_justification,
            changed_by=current_user.username,
        )
        db.commit()
        db.refresh(obj)
        return obj

    @staticmethod
    def delete(
        db: Session, *, region_id: int, current_user: User, justification: str | None = None
    ) -> None:
        """Desactiva región (soft delete) y deja trazabilidad."""
        obj = RegionRepository.get_by_id(db, region_id)
        if not obj:
            raise NotFoundError("No encontrado.")
        old_name = obj.name
        clean_justification = RegionService._require_justification_if_used(
            db, region_id=obj.id, justification=justification
        )
        RegionRepository.deactivate(obj)
        CatalogChangeLogRepository.create(
            db,
            entity_type="region",
            entity_id=obj.id,
            action="DEACTIVATE",
            old_name=old_name,
            new_name=old_name,
            justification=clean_justification,
            changed_by=current_user.username,
        )
        db.commit()


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Proteger consistencia del catálogo de regiones y su historial de cambios.
#
# Posibles mejoras:
# - Validar dependencias activas antes de desactivar región.
#
# Riesgos en producción:
# - Desactivación de regiones muy referenciadas puede impactar configuración de escenarios.
#
# Escalabilidad:
# - I/O-bound, costo bajo por transacción.

