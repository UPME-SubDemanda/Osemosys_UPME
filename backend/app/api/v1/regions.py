"""Endpoints para catálogo `Region`."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_catalog_manager, get_current_user
from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import get_db
from app.models import Region, User
from app.schemas.pagination import PaginatedResponse
from app.schemas.region import RegionCreate, RegionPublic, RegionUpdate
from app.services.region_service import RegionService

router = APIRouter(prefix="/regions")


@router.get("", response_model=PaginatedResponse[RegionPublic])
def list_regions(
    busqueda: str | None = None,
    include_inactive: bool = False,
    cantidad: int | None = 25,
    offset: int | None = 1,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Lista regiones activas con paginación."""
    return RegionService.list(
        db,
        busqueda=busqueda,
        is_active=None if include_inactive else True,
        cantidad=cantidad,
        offset=offset,
    )


@router.get("/desactivados", response_model=PaginatedResponse[RegionPublic])
def list_inactive_regions(
    busqueda: str | None = None,
    cantidad: int | None = 25,
    offset: int | None = 1,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Lista regiones inactivas por soft delete."""
    return RegionService.list_inactive(db, busqueda=busqueda, cantidad=cantidad, offset=offset)


@router.post("", response_model=RegionPublic, status_code=201)
def create_region(
    payload: RegionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> Region:
    """Crea una región de catálogo (requiere permiso administrador de catálogos)."""
    try:
        return RegionService.create(db, name=payload.name, current_user=current_user)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.put("/{region_id}", response_model=RegionPublic)
def update_region(
    region_id: int,
    payload: RegionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> Region:
    """Actualiza región existente por id."""
    try:
        return RegionService.update(
            db,
            region_id=region_id,
            name=payload.name,
            current_user=current_user,
            justification=payload.justification,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.delete("/{region_id}")
def delete_region(
    region_id: int,
    justification: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict[str, str]:
    """Desactiva lógicamente una región."""
    try:
        RegionService.delete(
            db,
            region_id=region_id,
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
# - Exponer API REST para administración de regiones.
#
# Posibles mejoras:
# - Evitar desactivación cuando la región esté referenciada en escenarios críticos.
#
# Riesgos en producción:
# - Inconsistencia funcional si se desactiva una región aún usada por procesos activos.
#
# Escalabilidad:
# - Tráfico bajo/medio, dominado por consultas de catálogo.

