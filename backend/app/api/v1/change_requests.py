"""Endpoints para ciclo de vida de solicitudes de cambio.

Crear solicitud sobre valor OSeMOSYS, listar propias, listar pendientes por escenario,
aprobar o rechazar (requiere permisos sobre el escenario).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.session import get_db
from app.models import User
from app.schemas.change_request import ChangeRequestCreate, ChangeRequestPublic
from app.services.change_request_service import ChangeRequestService

router = APIRouter(prefix="/change-requests")


@router.post("", response_model=ChangeRequestPublic, status_code=201)
def create_change_request(
    payload: ChangeRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Crea una solicitud de cambio sobre un valor existente.

    Método HTTP:
        - `POST` por creación de solicitud no idempotente.
    """
    try:
        return ChangeRequestService.create(
            db,
            current_user=current_user,
            id_osemosys_param_value=payload.id_osemosys_param_value,
            new_value=payload.new_value,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.get("/mine", response_model=list[ChangeRequestPublic])
def list_my_change_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Lista solicitudes creadas por el usuario autenticado."""
    return ChangeRequestService.list_my_requests(db, current_user=current_user)


@router.get("/pending/{scenario_id}", response_model=list[ChangeRequestPublic])
def list_pending_by_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Lista solicitudes pendientes para revisión en un escenario."""
    try:
        return ChangeRequestService.list_pending_by_scenario(
            db, scenario_id=scenario_id, current_user=current_user
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e


@router.post("/{change_request_id}/approve", response_model=ChangeRequestPublic)
def approve_change_request(
    change_request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Aprueba una solicitud pendiente.

    Método HTTP:
        - `POST` por tratarse de transición de estado de dominio.
    """
    try:
        return ChangeRequestService.approve(
            db, current_user=current_user, change_request_id=change_request_id
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.post("/{change_request_id}/reject", response_model=ChangeRequestPublic)
def reject_change_request(
    change_request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Rechaza una solicitud pendiente."""
    try:
        return ChangeRequestService.reject(
            db, current_user=current_user, change_request_id=change_request_id
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Coordinar flujo de gobernanza de cambios sobre parámetros de escenarios.
#
# Posibles mejoras:
# - Incorporar workflow configurable (multi-aprobador, SLA, auditoría ampliada).
#
# Riesgos en producción:
# - Rutas de aprobación/rechazo sin idempotencia explícita pueden provocar carreras
#   en revisiones concurrentes.
#
# Escalabilidad:
# - Carga moderada; principalmente I/O-bound y dependiente de índices por estado.
