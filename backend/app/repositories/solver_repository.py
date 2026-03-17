"""Repositorio para catálogo `Solver`."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Solver


class SolverRepository:
    """Acceso a datos de solvers configurados."""

    @staticmethod
    def get_paginated(
        db: Session,
        *,
        busqueda: str | None,
        is_active: bool | None,
        row_offset: int,
        limit: int,
    ) -> tuple[list[Solver], int]:
        """Consulta paginada de solvers."""
        stmt = select(Solver)
        count_stmt = select(func.count()).select_from(Solver)
        if is_active is not None:
            state_filter = Solver.is_active.is_(is_active)
            stmt = stmt.where(state_filter)
            count_stmt = count_stmt.where(state_filter)
        if busqueda:
            search_filter = Solver.name.ilike(f"%{busqueda}%")
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        total = int(db.scalar(count_stmt) or 0)
        items = (
            db.execute(stmt.order_by(Solver.name.asc()).offset(row_offset).limit(limit))
            .scalars()
            .all()
        )
        return list(items), total

    @staticmethod
    def get_by_id(db: Session, solver_id: int) -> Solver | None:
        """Obtiene solver por id."""
        return db.get(Solver, solver_id)

    @staticmethod
    def create(db: Session, *, name: str) -> Solver:
        """Inserta solver."""
        obj = Solver(name=name)
        db.add(obj)
        return obj

    @staticmethod
    def deactivate(obj: Solver) -> None:
        """Desactiva solver de forma lógica."""
        obj.is_active = False


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Persistencia de catálogo de solvers disponibles.
#
# Posibles mejoras:
# - Incorporar campos de capacidad y compatibilidad por solver.
#
# Riesgos en producción:
# - Cambios de catálogo sin coordinación pueden impactar jobs encolados.
#
# Escalabilidad:
# - I/O-bound.

