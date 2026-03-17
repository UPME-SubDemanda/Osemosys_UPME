"""Servicio de negocio para catálogo `Solver`."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models import ParameterValue, SimulationJob, User
from app.repositories.catalog_change_log_repository import CatalogChangeLogRepository
from app.repositories.solver_repository import SolverRepository
from app.services.pagination import build_meta, normalize_pagination


class SolverService:
    """Administra catálogo de solvers permitidos en la plataforma."""

    @staticmethod
    @staticmethod
    def _is_used(db: Session, *, solver_id: int, solver_name: str) -> bool:
        in_parameter_value = (
            db.query(ParameterValue.id).filter(ParameterValue.id_solver == solver_id).limit(1).first() is not None
        )
        in_simulation_jobs = (
            db.query(SimulationJob.id).filter(SimulationJob.solver_name == solver_name).limit(1).first()
            is not None
        )
        return in_parameter_value or in_simulation_jobs

    @staticmethod
    def _require_justification_if_used(
        db: Session, *, solver_id: int, solver_name: str, justification: str | None
    ) -> str | None:
        clean = (justification or "").strip() or None
        if SolverService._is_used(db, solver_id=solver_id, solver_name=solver_name) and not clean:
            raise ConflictError(
                "Este solver ya está utilizado en escenarios. Debes enviar una justificación."
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
        """Lista solvers según estado y texto de búsqueda."""
        page, page_size, row_offset = normalize_pagination(offset, cantidad)
        items, total = SolverRepository.get_paginated(
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
        """Lista solvers desactivados."""
        return SolverService.list(
            db,
            busqueda=busqueda,
            is_active=False,
            cantidad=cantidad,
            offset=offset,
        )

    @staticmethod
    def create(db: Session, *, name: str, current_user: User):
        """Crea solver y registra cambio."""
        obj = SolverRepository.create(db, name=name)
        try:
            db.flush()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("Ya existe un registro con ese nombre.") from e
        CatalogChangeLogRepository.create(
            db,
            entity_type="solver",
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
        solver_id: int,
        name: str,
        current_user: User,
        justification: str | None = None,
    ):
        """Actualiza nombre de solver con manejo de integridad."""
        obj = SolverRepository.get_by_id(db, solver_id)
        if not obj:
            raise NotFoundError("No encontrado.")
        old_name = obj.name
        clean_justification = SolverService._require_justification_if_used(
            db, solver_id=obj.id, solver_name=old_name, justification=justification
        )
        obj.name = name
        try:
            db.flush()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("Ya existe un registro con ese nombre.") from e
        CatalogChangeLogRepository.create(
            db,
            entity_type="solver",
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
        db: Session, *, solver_id: int, current_user: User, justification: str | None = None
    ) -> None:
        """Desactiva solver para impedir su uso futuro."""
        obj = SolverRepository.get_by_id(db, solver_id)
        if not obj:
            raise NotFoundError("No encontrado.")
        old_name = obj.name
        clean_justification = SolverService._require_justification_if_used(
            db, solver_id=obj.id, solver_name=old_name, justification=justification
        )
        SolverRepository.deactivate(obj)
        CatalogChangeLogRepository.create(
            db,
            entity_type="solver",
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
# - Gobernar catálogo de solvers configurables y auditar cambios.
#
# Posibles mejoras:
# - Asociar metadata técnica (versión, flags soportados) por solver.
#
# Riesgos en producción:
# - Desactivar solver en uso sin plan de migración puede romper jobs.
#
# Escalabilidad:
# - I/O-bound; adecuado para operación concurrente moderada.

