"""CRUD del catálogo de etiquetas de escenario (prioridad y color)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_catalog_manager, get_current_user
from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import get_db
from app.models import User
from app.schemas.scenario import ScenarioTagCreate, ScenarioTagPublic, ScenarioTagUpdate
from app.services.scenario_tag_service import ScenarioTagService

router = APIRouter(prefix="/scenario-tags")


@router.get("", response_model=list[ScenarioTagPublic])
def list_scenario_tags(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ScenarioTagPublic]:
    rows = ScenarioTagService.list_all(db)
    return [ScenarioTagPublic.model_validate(r) for r in rows]


@router.post("", response_model=ScenarioTagPublic, status_code=201)
def create_scenario_tag(
    payload: ScenarioTagCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_catalog_manager),
) -> ScenarioTagPublic:
    try:
        row = ScenarioTagService.create(
            db,
            name=payload.name,
            color=payload.color,
            sort_order=payload.sort_order,
        )
        return ScenarioTagPublic.model_validate(row)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.patch("/{tag_id}", response_model=ScenarioTagPublic)
def update_scenario_tag(
    tag_id: int,
    payload: ScenarioTagUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_catalog_manager),
) -> ScenarioTagPublic:
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=422, detail="No hay campos para actualizar.")
    try:
        row = ScenarioTagService.update(
            db,
            tag_id=tag_id,
            name=data.get("name"),
            color=data.get("color"),
            sort_order=data.get("sort_order"),
        )
        return ScenarioTagPublic.model_validate(row)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.delete("/{tag_id}", status_code=204)
def delete_scenario_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_catalog_manager),
) -> None:
    try:
        ScenarioTagService.delete(db, tag_id=tag_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
