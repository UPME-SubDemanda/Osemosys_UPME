"""Repositorio para catálogo `Emission`."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Emission


class EmissionRepository:
    """Acceso a datos de emisiones."""

    @staticmethod
    def get_paginated(
        db: Session,
        *,
        busqueda: str | None,
        is_active: bool | None,
        row_offset: int,
        limit: int,
    ) -> tuple[list[Emission], int]:
        """Lista emisiones paginadas para filtros de catálogo."""
        stmt = select(Emission)
        count_stmt = select(func.count()).select_from(Emission)
        if is_active is not None:
            state_filter = Emission.is_active.is_(is_active)
            stmt = stmt.where(state_filter)
            count_stmt = count_stmt.where(state_filter)
        if busqueda:
            search_filter = Emission.name.ilike(f"%{busqueda}%")
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        total = int(db.scalar(count_stmt) or 0)
        items = (
            db.execute(
                stmt.order_by(Emission.name.asc()).offset(row_offset).limit(limit)
            )
            .scalars()
            .all()
        )
        return list(items), total

    @staticmethod
    def get_by_id(db: Session, emission_id: int) -> Emission | None:
        """Obtiene emisión por id."""
        return db.get(Emission, emission_id)

    @staticmethod
    def create(db: Session, *, name: str) -> Emission:
        """Crea entidad de emisión."""
        obj = Emission(name=name)
        db.add(obj)
        return obj

    @staticmethod
    def deactivate(obj: Emission) -> None:
        """Aplica desactivación lógica."""
        obj.is_active = False


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Persistir y consultar catálogo de emisiones.
#
# Posibles mejoras:
# - Filtros por alcances/reglas regulatorias.
#
# Riesgos en producción:
# - Cardinalidad alta más `ilike` puede afectar tiempos de respuesta.
#
# Escalabilidad:
# - I/O-bound.

