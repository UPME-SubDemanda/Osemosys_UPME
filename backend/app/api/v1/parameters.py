"""Endpoints para catálogo Parameter.

Define nombres de parámetros usados por el modelo energético. CRUD con soft delete;
crear/actualizar/eliminar requiere permiso can_manage_catalogs.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_catalog_manager, get_current_user
from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import get_db
from app.models import Parameter, User
from app.schemas.pagination import PaginatedResponse
from app.schemas.parameter import ParameterCreate, ParameterPublic, ParameterUpdate
from app.services.parameter_service import ParameterService

router = APIRouter(prefix="/parameters")


@router.get("", response_model=PaginatedResponse[ParameterPublic])
def list_parameters(
    busqueda: str | None = None,
    include_inactive: bool = False,
    cantidad: int | None = 25,
    offset: int | None = 1,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Lista parámetros activos con paginación.

    Respuestas:
        - 200: listado paginado.
        - 401: usuario no autenticado.
    """
    return ParameterService.list(
        db,
        busqueda=busqueda,
        is_active=None if include_inactive else True,
        cantidad=cantidad,
        offset=offset,
    )


@router.get("/desactivados", response_model=PaginatedResponse[ParameterPublic])
def list_inactive_parameters(
    busqueda: str | None = None,
    cantidad: int | None = 25,
    offset: int | None = 1,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Lista parámetros desactivados (soft delete)."""
    return ParameterService.list_inactive(db, busqueda=busqueda, cantidad=cantidad, offset=offset)


@router.post("", response_model=ParameterPublic, status_code=201)
def create_parameter(
    payload: ParameterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> Parameter:
    """Crea un parámetro de catálogo.

    Método HTTP:
        - `POST` por creación de recurso.

    Seguridad:
        - restringido a usuarios con permiso de catálogo.
    """
    try:
        return ParameterService.create(db, name=payload.name, current_user=current_user)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.put("/{parameter_id}", response_model=ParameterPublic)
def update_parameter(
    parameter_id: int,
    payload: ParameterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> Parameter:
    """Actualiza nombre de parámetro existente (`PUT`)."""
    try:
        return ParameterService.update(
            db,
            parameter_id=parameter_id,
            name=payload.name,
            current_user=current_user,
            justification=payload.justification,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.delete("/{parameter_id}")
def delete_parameter(
    parameter_id: int,
    justification: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict[str, str]:
    """Aplica soft delete sobre parámetro (`DELETE` lógico)."""
    try:
        ParameterService.delete(
            db,
            parameter_id=parameter_id,
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
# - Gestionar CRUD lógico de catálogo de parámetros.
#
# Posibles mejoras:
# - Añadir validación de naming convention para compatibilidad OSEMOSYS.
#
# Riesgos en producción:
# - Cambios de nombre pueden romper mapeo semántico de loader si no hay gobernanza.
#
# Escalabilidad:
# - Operaciones I/O-bound de baja complejidad.

