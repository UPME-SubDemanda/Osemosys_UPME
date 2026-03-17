"""Servicio de negocio para catálogo `Technology`."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models import OsemosysParamValue, ParameterValue, User
from app.repositories.catalog_change_log_repository import CatalogChangeLogRepository
from app.repositories.technology_repository import TechnologyRepository
from app.services.pagination import build_meta, normalize_pagination


class TechnologyService:
    """Operaciones de negocio para tecnologías del sistema energético."""

    @staticmethod
    @staticmethod
    def _is_used(db: Session, *, technology_id: int) -> bool:
        in_parameter_value = (
            db.query(ParameterValue.id)
            .filter(ParameterValue.id_technology == technology_id)
            .limit(1)
            .first()
            is not None
        )
        in_osemosys_value = (
            db.query(OsemosysParamValue.id)
            .filter(OsemosysParamValue.id_technology == technology_id)
            .limit(1)
            .first()
            is not None
        )
        return in_parameter_value or in_osemosys_value

    @staticmethod
    def _require_justification_if_used(
        db: Session, *, technology_id: int, justification: str | None
    ) -> str | None:
        clean = (justification or "").strip() or None
        if TechnologyService._is_used(db, technology_id=technology_id) and not clean:
            raise ConflictError(
                "Esta tecnología ya está utilizada en escenarios. Debes enviar una justificación."
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
        """Lista tecnologías filtradas por búsqueda y estado activo."""
        page, page_size, row_offset = normalize_pagination(offset, cantidad)
        items, total = TechnologyRepository.get_paginated(
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
        """Lista tecnologías en estado inactivo."""
        return TechnologyService.list(
            db,
            busqueda=busqueda,
            is_active=False,
            cantidad=cantidad,
            offset=offset,
        )

    @staticmethod
    def create(db: Session, *, name: str, current_user: User):
        """Crea tecnología y registra auditoría."""
        obj = TechnologyRepository.create(db, name=name)
        try:
            db.flush()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("Ya existe un registro con ese nombre.") from e
        CatalogChangeLogRepository.create(
            db,
            entity_type="technology",
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
        technology_id: int,
        name: str,
        current_user: User,
        justification: str | None = None,
    ):
        """Actualiza tecnología existente con control de unicidad."""
        obj = TechnologyRepository.get_by_id(db, technology_id)
        if not obj:
            raise NotFoundError("No encontrado.")
        old_name = obj.name
        clean_justification = TechnologyService._require_justification_if_used(
            db, technology_id=obj.id, justification=justification
        )
        obj.name = name
        try:
            db.flush()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("Ya existe un registro con ese nombre.") from e
        CatalogChangeLogRepository.create(
            db,
            entity_type="technology",
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
        db: Session, *, technology_id: int, current_user: User, justification: str | None = None
    ) -> None:
        """Desactiva tecnología sin eliminarla físicamente."""
        obj = TechnologyRepository.get_by_id(db, technology_id)
        if not obj:
            raise NotFoundError("No encontrado.")
        old_name = obj.name
        clean_justification = TechnologyService._require_justification_if_used(
            db, technology_id=obj.id, justification=justification
        )
        TechnologyRepository.deactivate(obj)
        CatalogChangeLogRepository.create(
            db,
            entity_type="technology",
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
# - Administrar el catálogo de tecnologías con trazabilidad operativa.
#
# Posibles mejoras:
# - Bloquear desactivación si la tecnología está en escenarios críticos activos.
#
# Riesgos en producción:
# - Cambios no controlados en taxonomía de tecnologías afectan comparabilidad histórica.
#
# Escalabilidad:
# - Patrón I/O-bound simple; escala con la base de datos.

