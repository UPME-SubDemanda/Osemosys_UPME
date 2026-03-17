"""Endpoints para catálogo `Fuel`."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_catalog_manager, get_current_user
from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import get_db
from app.models import Fuel, User
from app.schemas.pagination import PaginatedResponse
from app.schemas.fuel import FuelCreate, FuelPublic, FuelUpdate
from app.services.fuel_service import FuelService

router = APIRouter(prefix="/fuels")


@router.get("", response_model=PaginatedResponse[FuelPublic])
def list_fuels(
    busqueda: str | None = None,
    include_inactive: bool = False,
    cantidad: int | None = 25,
    offset: int | None = 1,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Lista combustibles activos con paginación."""
    return FuelService.list(
        db,
        busqueda=busqueda,
        is_active=None if include_inactive else True,
        cantidad=cantidad,
        offset=offset,
    )


@router.get("/desactivados", response_model=PaginatedResponse[FuelPublic])
def list_inactive_fuels(
    busqueda: str | None = None,
    cantidad: int | None = 25,
    offset: int | None = 1,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Lista combustibles inactivos por soft delete."""
    return FuelService.list_inactive(db, busqueda=busqueda, cantidad=cantidad, offset=offset)


@router.post("", response_model=FuelPublic, status_code=201)
def create_fuel(
    payload: FuelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> Fuel:
    """Crea combustible de catálogo (controlado por permisos)."""
    try:
        return FuelService.create(db, name=payload.name, current_user=current_user)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.put("/{fuel_id}", response_model=FuelPublic)
def update_fuel(
    fuel_id: int,
    payload: FuelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> Fuel:
    """Actualiza combustible por identificador."""
    try:
        return FuelService.update(
            db,
            fuel_id=fuel_id,
            name=payload.name,
            current_user=current_user,
            justification=payload.justification,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.delete("/{fuel_id}")
def delete_fuel(
    fuel_id: int,
    justification: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict[str, str]:
    """Desactiva combustible en lugar de eliminar físicamente."""
    try:
        FuelService.delete(
            db,
            fuel_id=fuel_id,
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
# - Gestionar ciclo de vida del catálogo de combustibles.
#
# Posibles mejoras:
# - Añadir validación de relaciones activas antes de desactivar.
#
# Riesgos en producción:
# - Desactivaciones sin análisis de impacto pueden alterar escenarios existentes.
#
# Escalabilidad:
# - Componente de baja complejidad y baja presión de CPU.

