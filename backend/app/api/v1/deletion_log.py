"""Endpoint de lectura para la bitácora de eliminaciones.

Cualquier usuario autenticado puede consultar el historial — la información
es auditoría de gobernanza, no PII sensible. Pagina por `cantidad`/`offset`
y admite filtros por `entity_type` y rango de fechas.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import DeletionLog, User
from app.schemas.deletion_log import DeletionLogPage, DeletionLogPublic
from app.schemas.pagination import PaginationMeta

router = APIRouter(prefix="/deletion-log")


@router.get("", response_model=DeletionLogPage)
def list_deletion_log(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # noqa: ARG001 — auth only
    entity_type: str | None = Query(default=None, description="SCENARIO | SIMULATION_JOB"),
    username: str | None = Query(default=None, description="Filtro por usuario eliminador"),
    from_date: datetime | None = Query(default=None, description="ISO 8601"),
    to_date: datetime | None = Query(default=None, description="ISO 8601"),
    cantidad: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=1, ge=1),
) -> dict:
    stmt = select(DeletionLog)
    if entity_type:
        stmt = stmt.where(DeletionLog.entity_type == entity_type)
    if username:
        stmt = stmt.where(DeletionLog.deleted_by_username == username)
    if from_date:
        stmt = stmt.where(DeletionLog.deleted_at >= from_date)
    if to_date:
        stmt = stmt.where(DeletionLog.deleted_at <= to_date)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    stmt = stmt.order_by(DeletionLog.deleted_at.desc()).limit(cantidad).offset((offset - 1) * cantidad)
    rows = db.scalars(stmt).all()

    return {
        "meta": PaginationMeta(
            page=offset,
            page_size=cantidad,
            total=total,
            total_pages=PaginationMeta.compute_total_pages(total, cantidad),
        ),
        "data": [
            DeletionLogPublic(
                id=r.id,
                entity_type=r.entity_type,
                entity_id=r.entity_id,
                entity_name=r.entity_name,
                deleted_by_user_id=str(r.deleted_by_user_id),
                deleted_by_username=r.deleted_by_username,
                deleted_at=r.deleted_at,
                details_json=r.details_json,
            )
            for r in rows
        ],
    }
