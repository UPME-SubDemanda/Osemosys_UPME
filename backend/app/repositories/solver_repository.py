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
        is_active: bool,
        row_offset: int,
        limit: int,
    ) -> tuple[list[Solver], int]:
        """Consulta paginada de solvers."""
        cond = Solver.is_active.is_(is_active)
        if busqueda:
            cond = cond & Solver.name.ilike(f"%{busqueda}%")

        total = int(db.scalar(select(func.count()).select_from(Solver).where(cond)) or 0)
        items = (
            db.execute(select(Solver).where(cond).order_by(Solver.name.asc()).offset(row_offset).limit(limit))
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

