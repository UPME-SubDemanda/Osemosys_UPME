"""Repositorio para catálogo `Parameter`."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Parameter


class ParameterRepository:
    """Acceso a datos de parámetros de catálogo."""

    @staticmethod
    def get_paginated(
        db: Session,
        *,
        busqueda: str | None,
        is_active: bool | None,
        row_offset: int,
        limit: int,
    ) -> tuple[list[Parameter], int]:
        """Retorna lote paginado y total para filtros de catálogo."""
        stmt = select(Parameter)
        count_stmt = select(func.count()).select_from(Parameter)
        if is_active is not None:
            state_filter = Parameter.is_active.is_(is_active)
            stmt = stmt.where(state_filter)
            count_stmt = count_stmt.where(state_filter)
        if busqueda:
            search_filter = Parameter.name.ilike(f"%{busqueda}%")
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        total = int(db.scalar(count_stmt) or 0)
        items = (
            db.execute(
                stmt
                .order_by(Parameter.name.asc())
                .offset(row_offset)
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return list(items), total

    @staticmethod
    def get_by_id(db: Session, parameter_id: int) -> Parameter | None:
        """Obtiene parámetro por id."""
        return db.get(Parameter, parameter_id)

    @staticmethod
    def create(db: Session, *, name: str) -> Parameter:
        """Construye e inserta nueva entidad `Parameter`."""
        obj = Parameter(name=name)
        db.add(obj)
        return obj

    @staticmethod
    def deactivate(obj: Parameter) -> None:
        """Aplica desactivación lógica."""
        obj.is_active = False


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Encapsular consultas y mutaciones simples del catálogo de parámetros.
#
# Posibles mejoras:
# - Migrar filtros `ilike` a búsqueda full-text cuando crezca volumen.
#
# Riesgos en producción:
# - Offset pagination en páginas altas puede ser costosa.
#
# Escalabilidad:
# - I/O-bound; buena para volumen medio con índices por `name`/`is_active`.

