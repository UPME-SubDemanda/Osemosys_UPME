"""Repositorio para catálogo `Fuel`."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Fuel


class FuelRepository:
    """Acceso a datos de combustibles."""

    @staticmethod
    def get_paginated(
        db: Session,
        *,
        busqueda: str | None,
        is_active: bool,
        row_offset: int,
        limit: int,
    ) -> tuple[list[Fuel], int]:
        """Consulta paginada de combustibles."""
        cond = Fuel.is_active.is_(is_active)
        if busqueda:
            cond = cond & Fuel.name.ilike(f"%{busqueda}%")

        total = int(db.scalar(select(func.count()).select_from(Fuel).where(cond)) or 0)
        items = (
            db.execute(select(Fuel).where(cond).order_by(Fuel.name.asc()).offset(row_offset).limit(limit))
            .scalars()
            .all()
        )
        return list(items), total

    @staticmethod
    def get_by_id(db: Session, fuel_id: int) -> Fuel | None:
        """Obtiene combustible por id."""
        return db.get(Fuel, fuel_id)

    @staticmethod
    def create(db: Session, *, name: str) -> Fuel:
        """Crea combustible."""
        obj = Fuel(name=name)
        db.add(obj)
        return obj

    @staticmethod
    def deactivate(obj: Fuel) -> None:
        """Soft delete de combustible."""
        obj.is_active = False


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - CRUD de persistencia para catálogo de combustibles.
#
# Posibles mejoras:
# - Consultas por tipo de combustible o atributos extensibles.
#
# Riesgos en producción:
# - Consultas de texto libres pueden ser costosas sin tuning.
#
# Escalabilidad:
# - I/O-bound.

