"""Endpoints para gestión de `parameter_value` (valores por defecto globales)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import get_db
from app.models import ParameterValue, User
from app.schemas.parameter_value import ParameterValueCreate, ParameterValuePublic, ParameterValueUpdate
from app.services.parameter_value_service import ParameterValueService

router = APIRouter(prefix="/parameter-values")


@router.get("", response_model=list[ParameterValuePublic])
def list_parameter_values(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ParameterValue]:
    """Lista todos los valores por defecto de parámetros."""
    return ParameterValueService.list_all(db)


@router.post("", response_model=ParameterValuePublic, status_code=201)
def create_parameter_value(
    payload: ParameterValueCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ParameterValue:
    """Crea un valor por defecto de parámetro."""
    try:
        return ParameterValueService.create(db, payload=payload.model_dump())
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.put("/{parameter_value_id}", response_model=ParameterValuePublic)
def update_parameter_value(
    parameter_value_id: int,
    payload: ParameterValueUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ParameterValue:
    """Actualiza valor/unidad de un `parameter_value` existente."""
    try:
        return ParameterValueService.update(
            db,
            parameter_value_id=parameter_value_id,
            value=payload.value,
            unit=payload.unit,
            changed_by=current_user.username,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
