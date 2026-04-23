"""CRUD del catálogo de categorías jerárquicas de etiquetas de escenario."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_catalog_manager, get_current_user
from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import get_db
from app.models import User
from app.schemas.scenario import (
    ScenarioTagCategoryCreate,
    ScenarioTagCategoryPublic,
    ScenarioTagCategoryUpdate,
)
from app.services.scenario_tag_category_service import ScenarioTagCategoryService

router = APIRouter(prefix="/scenario-tag-categories")


@router.get("", response_model=list[ScenarioTagCategoryPublic])
def list_categories(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ScenarioTagCategoryPublic]:
    rows = ScenarioTagCategoryService.list_all(db)
    return [ScenarioTagCategoryPublic.model_validate(r) for r in rows]


@router.post("", response_model=ScenarioTagCategoryPublic, status_code=201)
def create_category(
    payload: ScenarioTagCategoryCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_catalog_manager),
) -> ScenarioTagCategoryPublic:
    try:
        row = ScenarioTagCategoryService.create(
            db,
            name=payload.name,
            hierarchy_level=payload.hierarchy_level,
            sort_order=payload.sort_order,
            max_tags_per_scenario=payload.max_tags_per_scenario,
            is_exclusive_combination=payload.is_exclusive_combination,
            default_color=payload.default_color,
        )
        return ScenarioTagCategoryPublic.model_validate(row)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.patch("/{category_id}", response_model=ScenarioTagCategoryPublic)
def update_category(
    category_id: int,
    payload: ScenarioTagCategoryUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_catalog_manager),
) -> ScenarioTagCategoryPublic:
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=422, detail="No hay campos para actualizar.")
    try:
        row = ScenarioTagCategoryService.update(
            db,
            category_id=category_id,
            name=data.get("name"),
            hierarchy_level=data.get("hierarchy_level"),
            sort_order=data.get("sort_order"),
            max_tags_per_scenario=data.get("max_tags_per_scenario"),
            is_exclusive_combination=data.get("is_exclusive_combination"),
            default_color=data.get("default_color"),
            max_tags_explicit="max_tags_per_scenario" in data,
        )
        return ScenarioTagCategoryPublic.model_validate(row)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.delete("/{category_id}", status_code=204)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_catalog_manager),
) -> None:
    try:
        ScenarioTagCategoryService.delete(db, category_id=category_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
