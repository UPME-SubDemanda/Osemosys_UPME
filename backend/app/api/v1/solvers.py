"""Endpoints para catálogo `Solver`."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_catalog_manager, get_current_user
from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import get_db
from app.models import Solver, User
from app.schemas.pagination import PaginatedResponse
from app.schemas.solver import SolverCreate, SolverPublic, SolverUpdate
from app.services.solver_service import SolverService

router = APIRouter(prefix="/solvers")


@router.get("", response_model=PaginatedResponse[SolverPublic])
def list_solvers(
    busqueda: str | None = None,
    include_inactive: bool = False,
    cantidad: int | None = 25,
    offset: int | None = 1,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Lista solvers activos disponibles para configuración de escenarios."""
    return SolverService.list(
        db,
        busqueda=busqueda,
        is_active=None if include_inactive else True,
        cantidad=cantidad,
        offset=offset,
    )


@router.get("/desactivados", response_model=PaginatedResponse[SolverPublic])
def list_inactive_solvers(
    busqueda: str | None = None,
    cantidad: int | None = 25,
    offset: int | None = 1,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Lista solvers desactivados."""
    return SolverService.list_inactive(db, busqueda=busqueda, cantidad=cantidad, offset=offset)


@router.post("", response_model=SolverPublic, status_code=201)
def create_solver(
    payload: SolverCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> Solver:
    """Crea registro de solver habilitado para uso del modelo."""
    try:
        return SolverService.create(db, name=payload.name, current_user=current_user)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.put("/{solver_id}", response_model=SolverPublic)
def update_solver(
    solver_id: int,
    payload: SolverUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> Solver:
    """Actualiza metadata básica de solver."""
    try:
        return SolverService.update(
            db,
            solver_id=solver_id,
            name=payload.name,
            current_user=current_user,
            justification=payload.justification,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.delete("/{solver_id}")
def delete_solver(
    solver_id: int,
    justification: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict[str, str]:
    """Desactiva solver para evitar nuevos usos sin borrar historial."""
    try:
        SolverService.delete(
            db,
            solver_id=solver_id,
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
# - Administrar catálogo de solvers configurables por negocio/modelado.
#
# Posibles mejoras:
# - Asociar capacidades por solver (LP/MILP/NLP) para validación previa.
#
# Riesgos en producción:
# - Configurar solver no compatible puede derivar en fallos de ejecución costosos.
#
# Escalabilidad:
# - Sin impacto material en throughput general.

