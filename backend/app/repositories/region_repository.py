"""Repositorio para catálogo `Region`."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Region


class RegionRepository:
    """Acceso a datos para regiones."""

    @staticmethod
    def get_paginated(
        db: Session,
        *,
        busqueda: str | None,
        is_active: bool | None,
        row_offset: int,
        limit: int,
    ) -> tuple[list[Region], int]:
        """Consulta paginada de regiones."""
        stmt = select(Region)
        count_stmt = select(func.count()).select_from(Region)
        if is_active is not None:
            state_filter = Region.is_active.is_(is_active)
            stmt = stmt.where(state_filter)
            count_stmt = count_stmt.where(state_filter)
        if busqueda:
            search_filter = Region.name.ilike(f"%{busqueda}%")
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        total = int(db.scalar(count_stmt) or 0)
        items = (
            db.execute(
                stmt.order_by(Region.name.asc()).offset(row_offset).limit(limit)
            )
            .scalars()
            .all()
        )
        return list(items), total

    @staticmethod
    def get_by_id(db: Session, region_id: int) -> Region | None:
        """Obtiene región por id."""
        return db.get(Region, region_id)

    @staticmethod
    def create(db: Session, *, name: str) -> Region:
        """Inserta una nueva región."""
        obj = Region(name=name)
        db.add(obj)
        return obj

    @staticmethod
    def deactivate(obj: Region) -> None:
        """Marca la región como inactiva."""
        obj.is_active = False


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Operaciones de persistencia del catálogo de regiones.
#
# Posibles mejoras:
# - Añadir consultas por códigos normalizados además de nombre.
#
# Riesgos en producción:
# - Búsquedas `ilike` extensas sin índices funcionales pueden ser costosas.
#
# Escalabilidad:
# - I/O-bound.

