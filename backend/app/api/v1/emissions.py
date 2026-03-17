"""Endpoints para catálogo `Emission`."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_catalog_manager, get_current_user
from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import get_db
from app.models import Emission, User
from app.schemas.pagination import PaginatedResponse
from app.schemas.emission import EmissionCreate, EmissionPublic, EmissionUpdate
from app.services.emission_service import EmissionService

router = APIRouter(prefix="/emissions")


@router.get("", response_model=PaginatedResponse[EmissionPublic])
def list_emissions(
    busqueda: str | None = None,
    include_inactive: bool = False,
    cantidad: int | None = 25,
    offset: int | None = 1,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Lista emisiones activas con paginación."""
    return EmissionService.list(
        db,
        busqueda=busqueda,
        is_active=None if include_inactive else True,
        cantidad=cantidad,
        offset=offset,
    )


@router.get("/desactivados", response_model=PaginatedResponse[EmissionPublic])
def list_inactive_emissions(
    busqueda: str | None = None,
    cantidad: int | None = 25,
    offset: int | None = 1,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Lista emisiones inactivas."""
    return EmissionService.list_inactive(db, busqueda=busqueda, cantidad=cantidad, offset=offset)


@router.post("", response_model=EmissionPublic, status_code=201)
def create_emission(
    payload: EmissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> Emission:
    """Crea emisión de catálogo bajo autorización administrativa."""
    try:
        return EmissionService.create(db, name=payload.name, current_user=current_user)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.put("/{emission_id}", response_model=EmissionPublic)
def update_emission(
    emission_id: int,
    payload: EmissionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> Emission:
    """Actualiza emisión por id."""
    try:
        return EmissionService.update(
            db,
            emission_id=emission_id,
            name=payload.name,
            current_user=current_user,
            justification=payload.justification,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.delete("/{emission_id}")
def delete_emission(
    emission_id: int,
    justification: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict[str, str]:
    """Desactiva emisión (soft delete)."""
    try:
        EmissionService.delete(
            db,
            emission_id=emission_id,
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
# - Exponer administración de catálogo de emisiones para restricciones ambientales.
#
# Posibles mejoras:
# - Validar referencias cruzadas con parámetros de límite/penalización de emisiones.
#
# Riesgos en producción:
# - Modificaciones no controladas pueden sesgar cumplimiento regulatorio del modelo.
#
# Escalabilidad:
# - Operación principalmente I/O-bound con bajo costo.

