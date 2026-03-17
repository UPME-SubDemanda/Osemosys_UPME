"""Repositorio para catálogo `Technology`."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Technology


class TechnologyRepository:
    """Acceso a datos de tecnologías."""

    @staticmethod
    def get_paginated(
        db: Session,
        *,
        busqueda: str | None,
        is_active: bool,
        row_offset: int,
        limit: int,
    ) -> tuple[list[Technology], int]:
        """Devuelve tecnologías paginadas y total."""
        cond = Technology.is_active.is_(is_active)
        if busqueda:
            cond = cond & Technology.name.ilike(f"%{busqueda}%")

        total = int(db.scalar(select(func.count()).select_from(Technology).where(cond)) or 0)
        items = (
            db.execute(
                select(Technology)
                .where(cond)
                .order_by(Technology.name.asc())
                .offset(row_offset)
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return list(items), total

    @staticmethod
    def get_by_id(db: Session, technology_id: int) -> Technology | None:
        """Obtiene tecnología por id."""
        return db.get(Technology, technology_id)

    @staticmethod
    def create(db: Session, *, name: str) -> Technology:
        """Crea registro de tecnología."""
        obj = Technology(name=name)
        db.add(obj)
        return obj

    @staticmethod
    def deactivate(obj: Technology) -> None:
        """Desactiva lógicamente la tecnología."""
        obj.is_active = False


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Persistencia del catálogo tecnológico.
#
# Posibles mejoras:
# - Incluir filtros adicionales por familias tecnológicas.
#
# Riesgos en producción:
# - Ordenamiento por nombre puede ser sensible a collation.
#
# Escalabilidad:
# - I/O-bound.

