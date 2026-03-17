"""Servicio de negocio para catálogo `Parameter`.

Gestiona CRUD lógico y auditoría de cambios para parámetros de entrada del modelo.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models import OsemosysParamValue, ParameterValue, User
from app.repositories.catalog_change_log_repository import CatalogChangeLogRepository
from app.repositories.parameter_repository import ParameterRepository
from app.services.pagination import build_meta, normalize_pagination


class ParameterService:
    """Operaciones de negocio para parámetros de catálogo."""

    @staticmethod
    @staticmethod
    def _is_used(db: Session, *, parameter_id: int, parameter_name: str) -> bool:
        in_parameter_value = (
            db.query(ParameterValue.id)
            .filter(ParameterValue.id_parameter == parameter_id)
            .limit(1)
            .first()
            is not None
        )
        in_osemosys_value = (
            db.query(OsemosysParamValue.id)
            .filter(OsemosysParamValue.param_name == parameter_name)
            .limit(1)
            .first()
            is not None
        )
        return in_parameter_value or in_osemosys_value

    @staticmethod
    def _require_justification_if_used(
        db: Session, *, parameter_id: int, parameter_name: str, justification: str | None
    ) -> str | None:
        clean = (justification or "").strip() or None
        if ParameterService._is_used(db, parameter_id=parameter_id, parameter_name=parameter_name) and not clean:
            raise ConflictError(
                "Este parámetro ya está utilizado en escenarios. Debes enviar una justificación."
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
        """Lista parámetros por estado activo/inactivo con paginación."""
        page, page_size, row_offset = normalize_pagination(offset, cantidad)
        items, total = ParameterRepository.get_paginated(
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
        """Atajo para listar únicamente parámetros desactivados."""
        return ParameterService.list(
            db,
            busqueda=busqueda,
            is_active=False,
            cantidad=cantidad,
            offset=offset,
        )

    @staticmethod
    def create(db: Session, *, name: str, current_user: User):
        """Crea parámetro y registra auditoría de alta.

        Riesgo de concurrencia:
            - Condición de carrera en nombres duplicados se resuelve por constraint
              de BD y manejo de `IntegrityError`.
        """
        obj = ParameterRepository.create(db, name=name)
        try:
            db.flush()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("Ya existe un registro con ese nombre.") from e
        CatalogChangeLogRepository.create(
            db,
            entity_type="parameter",
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
        parameter_id: int,
        name: str,
        current_user: User,
        justification: str | None = None,
    ):
        """Actualiza nombre de parámetro y registra auditoría."""
        obj = ParameterRepository.get_by_id(db, parameter_id)
        if not obj:
            raise NotFoundError("No encontrado.")
        old_name = obj.name
        clean_justification = ParameterService._require_justification_if_used(
            db,
            parameter_id=obj.id,
            parameter_name=old_name,
            justification=justification,
        )
        obj.name = name
        try:
            db.flush()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("Ya existe un registro con ese nombre.") from e
        CatalogChangeLogRepository.create(
            db,
            entity_type="parameter",
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
        db: Session, *, parameter_id: int, current_user: User, justification: str | None = None
    ) -> None:
        """Aplica soft delete y registra evento de desactivación."""
        obj = ParameterRepository.get_by_id(db, parameter_id)
        if not obj:
            raise NotFoundError("No encontrado.")
        old_name = obj.name
        clean_justification = ParameterService._require_justification_if_used(
            db,
            parameter_id=obj.id,
            parameter_name=old_name,
            justification=justification,
        )
        ParameterRepository.deactivate(obj)
        CatalogChangeLogRepository.create(
            db,
            entity_type="parameter",
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
# - Aplicar reglas de negocio para catálogo de parámetros y trazabilidad de cambios.
#
# Posibles mejoras:
# - Validar taxonomía de nombres (`param_name`) acorde a loader OSEMOSYS.
#
# Riesgos en producción:
# - Renombres sin gobernanza pueden romper mapeo semántico hacia el modelo.
#
# Escalabilidad:
# - Operaciones I/O-bound de baja complejidad.

