"""Endpoints para catálogo `Technology`."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_catalog_manager, get_current_user
from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import get_db
from app.models import Technology, User
from app.schemas.pagination import PaginatedResponse
from app.schemas.technology import TechnologyCreate, TechnologyPublic, TechnologyUpdate
from app.services.technology_service import TechnologyService

router = APIRouter(prefix="/technologies")


@router.get("", response_model=PaginatedResponse[TechnologyPublic])
def list_technologies(
    busqueda: str | None = None,
    include_inactive: bool = False,
    cantidad: int | None = 25,
    offset: int | None = 1,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Lista tecnologías activas con paginación estándar."""
    return TechnologyService.list(
        db,
        busqueda=busqueda,
        is_active=None if include_inactive else True,
        cantidad=cantidad,
        offset=offset,
    )


@router.get("/desactivados", response_model=PaginatedResponse[TechnologyPublic])
def list_inactive_technologies(
    busqueda: str | None = None,
    cantidad: int | None = 25,
    offset: int | None = 1,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Lista tecnologías desactivadas."""
    return TechnologyService.list_inactive(db, busqueda=busqueda, cantidad=cantidad, offset=offset)


@router.post("", response_model=TechnologyPublic, status_code=201)
def create_technology(
    payload: TechnologyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> Technology:
    """Crea una tecnología de catálogo."""
    try:
        return TechnologyService.create(db, name=payload.name, current_user=current_user)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.put("/{technology_id}", response_model=TechnologyPublic)
def update_technology(
    technology_id: int,
    payload: TechnologyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> Technology:
    """Actualiza nombre de tecnología."""
    try:
        return TechnologyService.update(
            db,
            technology_id=technology_id,
            name=payload.name,
            current_user=current_user,
            justification=payload.justification,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.delete("/{technology_id}")
def delete_technology(
    technology_id: int,
    justification: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict[str, str]:
    """Desactiva tecnología (soft delete)."""
    try:
        TechnologyService.delete(
            db,
            technology_id=technology_id,
            current_user=current_user,
            justification=justification,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"status": "deactivated"}


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Administrar catálogo de tecnologías para el motor de optimización.
#
# Posibles mejoras:
# - Incorporar validaciones de integridad temporal por horizonte de escenarios.
#
# Riesgos en producción:
# - Cambios de tecnología impactan trazabilidad de resultados históricos.
#
# Escalabilidad:
# - Coste computacional bajo; I/O-bound en BD.

