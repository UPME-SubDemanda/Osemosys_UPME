"""Endpoints REST para ciclo de vida de simulaciones.

Expone: submit (crear job), list (listar jobs del usuario), get (detalle), cancel,
logs (eventos de ejecución), result (artefacto JSON de resultados).
Todos requieren usuario autenticado; delegan a SimulationService.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.session import get_db
from app.models import User
from app.schemas.pagination import PaginatedResponse
from app.schemas.simulation import (
    SimulationJobPublic,
    SimulationLogPublic,
    SimulationOverviewPublic,
    SimulationResultPublic,
    SimulationSubmit,
)
from app.services.simulation_service import SimulationService

router = APIRouter(prefix="/simulations")


@router.post("", response_model=SimulationJobPublic, status_code=201)
def submit_simulation(
    payload: SimulationSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Crea un job de simulación (HTTP POST).

    Se usa `POST` porque la operación crea un nuevo recurso en cola y no es idempotente.

    Validaciones delegadas al servicio:
    - escenario existente;
    - autorización del usuario sobre escenario;
    - límite de jobs activos por usuario.

    Respuestas:
    - 201: job encolado.
    - 404: escenario no encontrado.
    - 403: usuario sin acceso al escenario.
    - 409: límite de concurrencia por usuario excedido.
    """
    try:
        return SimulationService.submit(
            db,
            current_user=current_user,
            scenario_id=payload.scenario_id,
            solver_name=payload.solver_name,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.get("", response_model=PaginatedResponse[SimulationJobPublic])
def list_simulations(
    scope: str = "mine",
    status_filter: str | None = None,
    username: str | None = None,
    scenario_id: int | None = None,
    solver_name: str | None = None,
    cantidad: int | None = 25,
    offset: int | None = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Lista jobs del usuario autenticado con paginación estándar.

    Respuestas:
    - 200: listado paginado.

    Seguridad:
    - Solo retorna jobs pertenecientes al usuario autenticado.
    """
    return SimulationService.list_jobs(
        db,
        current_user=current_user,
        scope=scope,
        status=status_filter,
        username=username,
        scenario_id=scenario_id,
        solver_name=solver_name,
        cantidad=cantidad,
        offset=offset,
    )


@router.get("/overview", response_model=SimulationOverviewPublic)
def get_simulation_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Resumen global del tablero operativo de simulaciones."""
    return SimulationService.overview(db, current_user=current_user)


@router.get("/{job_id}", response_model=SimulationJobPublic)
def get_simulation(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Consulta un job puntual por `job_id` (HTTP GET).

    Respuestas:
    - 200: job encontrado y autorizado.
    - 404: job inexistente o no perteneciente al usuario.
    """
    try:
        return SimulationService.get_by_id(db, current_user=current_user, job_id=job_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{job_id}/cancel", response_model=SimulationJobPublic)
def cancel_simulation(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Solicita cancelación de un job (HTTP POST).

    Se usa `POST` porque representa una transición de estado con efecto lateral
    (acción de dominio), no una actualización parcial genérica del recurso.

    Respuestas:
    - 200: cancelación registrada/aplicada.
    - 404: job inexistente o no autorizado.
    - 409: job no cancelable por estado.
    """
    try:
        return SimulationService.cancel(db, current_user=current_user, job_id=job_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.get("/{job_id}/logs", response_model=PaginatedResponse[SimulationLogPublic])
def get_simulation_logs(
    job_id: int,
    cantidad: int | None = 50,
    offset: int | None = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Lista eventos de ejecución del job para trazabilidad operativa.

    Respuestas:
    - 200: logs paginados.
    - 404: job inexistente o no autorizado.
    """
    try:
        return SimulationService.list_logs(
            db,
            current_user=current_user,
            job_id=job_id,
            cantidad=cantidad,
            offset=offset,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{job_id}/result", response_model=SimulationResultPublic)
def get_simulation_result(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Retorna artefacto final de resultados de un job exitoso.

    Respuestas:
    - 200: resultado disponible.
    - 404: job no encontrado o artefacto no disponible.
    - 409: job aún no finaliza en estado exitoso.
    """
    try:
        return SimulationService.get_result(db, current_user=current_user, job_id=job_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Definir contrato HTTP de simulaciones y mapear errores de dominio a códigos REST.
#
# Posibles mejoras:
# - Documentar responses con ejemplos OpenAPI (`responses={...}`) por endpoint.
# - Añadir rate limiting por usuario para proteger infraestructura de ejecución.
#
# Riesgos en producción:
# - Sin controles de burst de submit, un actor autenticado puede saturar la cola.
# - Exposición de mensajes de error crudos puede filtrar detalles internos.
#
# Escalabilidad:
# - El módulo escala horizontalmente junto con API; cuello de botella real está
#   en worker CPU-bound y almacenamiento de eventos/artefactos.
