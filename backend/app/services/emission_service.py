"""Servicio de negocio para catálogo `Emission`."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models import OsemosysParamValue, ParameterValue, User
from app.repositories.catalog_change_log_repository import CatalogChangeLogRepository
from app.repositories.emission_repository import EmissionRepository
from app.services.pagination import build_meta, normalize_pagination


class EmissionService:
    """Reglas de negocio de emisiones y su trazabilidad."""

    @staticmethod
    @staticmethod
    def _is_used(db: Session, *, emission_id: int) -> bool:
        in_parameter_value = (
            db.query(ParameterValue.id).filter(ParameterValue.id_emission == emission_id).limit(1).first()
            is not None
        )
        in_osemosys_value = (
            db.query(OsemosysParamValue.id).filter(OsemosysParamValue.id_emission == emission_id).limit(1).first()
            is not None
        )
        return in_parameter_value or in_osemosys_value

    @staticmethod
    def _require_justification_if_used(
        db: Session, *, emission_id: int, justification: str | None
    ) -> str | None:
        clean = (justification or "").strip() or None
        if EmissionService._is_used(db, emission_id=emission_id) and not clean:
            raise ConflictError(
                "Esta emisión ya está utilizada en escenarios. Debes enviar una justificación."
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
        """Lista emisiones con paginación normalizada."""
        page, page_size, row_offset = normalize_pagination(offset, cantidad)
        items, total = EmissionRepository.get_paginated(
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
        """Lista emisiones inactivas."""
        return EmissionService.list(
            db,
            busqueda=busqueda,
            is_active=False,
            cantidad=cantidad,
            offset=offset,
        )

    @staticmethod
    def create(db: Session, *, name: str, current_user: User):
        """Crea factor/entidad de emisión y audita alta."""
        obj = EmissionRepository.create(db, name=name)
        try:
            db.flush()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("Ya existe un registro con ese nombre.") from e
        CatalogChangeLogRepository.create(
            db,
            entity_type="emission",
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
        emission_id: int,
        name: str,
        current_user: User,
        justification: str | None = None,
    ):
        """Actualiza emisión y persiste auditoría de modificación."""
        obj = EmissionRepository.get_by_id(db, emission_id)
        if not obj:
            raise NotFoundError("No encontrado.")
        old_name = obj.name
        clean_justification = EmissionService._require_justification_if_used(
            db, emission_id=obj.id, justification=justification
        )
        obj.name = name
        try:
            db.flush()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("Ya existe un registro con ese nombre.") from e
        CatalogChangeLogRepository.create(
            db,
            entity_type="emission",
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
        db: Session, *, emission_id: int, current_user: User, justification: str | None = None
    ) -> None:
        """Desactiva emisión sin borrado físico."""
        obj = EmissionRepository.get_by_id(db, emission_id)
        if not obj:
            raise NotFoundError("No encontrado.")
        old_name = obj.name
        clean_justification = EmissionService._require_justification_if_used(
            db, emission_id=obj.id, justification=justification
        )
        EmissionRepository.deactivate(obj)
        CatalogChangeLogRepository.create(
            db,
            entity_type="emission",
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
# - Gestionar catálogo de emisiones con consistencia y auditoría.
#
# Posibles mejoras:
# - Políticas de versionado para factores de emisión históricos.
#
# Riesgos en producción:
# - Cambios directos impactan resultados agregados de CO2e entre corridas.
#
# Escalabilidad:
# - I/O-bound; carga baja.

