"""Servicio de negocio para catálogo `Fuel`."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models import OsemosysParamValue, ParameterValue, User
from app.repositories.catalog_change_log_repository import CatalogChangeLogRepository
from app.repositories.fuel_repository import FuelRepository
from app.services.pagination import build_meta, normalize_pagination


class FuelService:
    """Orquesta reglas de negocio para combustibles."""

    @staticmethod
    @staticmethod
    def _is_used(db: Session, *, fuel_id: int) -> bool:
        in_parameter_value = (
            db.query(ParameterValue.id).filter(ParameterValue.id_fuel == fuel_id).limit(1).first() is not None
        )
        in_osemosys_value = (
            db.query(OsemosysParamValue.id).filter(OsemosysParamValue.id_fuel == fuel_id).limit(1).first()
            is not None
        )
        return in_parameter_value or in_osemosys_value

    @staticmethod
    def _require_justification_if_used(
        db: Session, *, fuel_id: int, justification: str | None
    ) -> str | None:
        clean = (justification or "").strip() or None
        if FuelService._is_used(db, fuel_id=fuel_id) and not clean:
            raise ConflictError(
                "Este combustible ya está utilizado en escenarios. Debes enviar una justificación."
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
        """Lista combustibles paginados con filtro textual."""
        page, page_size, row_offset = normalize_pagination(offset, cantidad)
        items, total = FuelRepository.get_paginated(
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
        """Lista combustibles desactivados."""
        return FuelService.list(
            db,
            busqueda=busqueda,
            is_active=False,
            cantidad=cantidad,
            offset=offset,
        )

    @staticmethod
    def create(db: Session, *, name: str, current_user: User):
        """Crea combustible y registra evento de catálogo."""
        obj = FuelRepository.create(db, name=name)
        try:
            db.flush()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("Ya existe un registro con ese nombre.") from e
        CatalogChangeLogRepository.create(
            db,
            entity_type="fuel",
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
        fuel_id: int,
        name: str,
        current_user: User,
        justification: str | None = None,
    ):
        """Actualiza combustible con manejo de conflicto por duplicado."""
        obj = FuelRepository.get_by_id(db, fuel_id)
        if not obj:
            raise NotFoundError("No encontrado.")
        old_name = obj.name
        clean_justification = FuelService._require_justification_if_used(
            db, fuel_id=obj.id, justification=justification
        )
        obj.name = name
        try:
            db.flush()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("Ya existe un registro con ese nombre.") from e
        CatalogChangeLogRepository.create(
            db,
            entity_type="fuel",
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
    def delete(db: Session, *, fuel_id: int, current_user: User, justification: str | None = None) -> None:
        """Realiza soft delete de combustible."""
        obj = FuelRepository.get_by_id(db, fuel_id)
        if not obj:
            raise NotFoundError("No encontrado.")
        old_name = obj.name
        clean_justification = FuelService._require_justification_if_used(
            db, fuel_id=obj.id, justification=justification
        )
        FuelRepository.deactivate(obj)
        CatalogChangeLogRepository.create(
            db,
            entity_type="fuel",
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
# - Encapsular CRUD lógico de combustibles y registro de auditoría.
#
# Posibles mejoras:
# - Incorporar validación de uso en constraints de emisiones antes de desactivar.
#
# Riesgos en producción:
# - Cambios frecuentes pueden introducir inconsistencias semánticas entre escenarios.
#
# Escalabilidad:
# - I/O-bound con baja latencia esperada.

