"""Asignación/quitado de etiquetas sobre un escenario concreto.

Usa `ScenarioService._require_admin` para validar que el usuario puede
modificar el escenario (owner o `can_edit_direct`).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.session import get_db
from app.models import User
from app.schemas.scenario import (
    ScenarioTagAssignRequest,
    ScenarioTagConflictDetail,
    ScenarioTagPublic,
)
from app.services.scenario_service import ScenarioService
from app.services.scenario_tag_assignment_service import (
    ScenarioTagAssignmentService,
    TagAssignmentConflict,
)

router = APIRouter(prefix="/scenarios")


@router.get("/{scenario_id}/tags", response_model=list[ScenarioTagPublic])
def list_scenario_tags_for_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ScenarioTagPublic]:
    try:
        ScenarioService._require_access(
            db, scenario_id=scenario_id, current_user=current_user
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    rows = ScenarioTagAssignmentService.list_tags(db, scenario_id=scenario_id)
    return [ScenarioTagPublic.model_validate(r) for r in rows]


@router.post("/{scenario_id}/tags", response_model=list[ScenarioTagPublic])
def assign_tag_to_scenario(
    scenario_id: int,
    payload: ScenarioTagAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ScenarioTagPublic]:
    try:
        ScenarioService._require_admin(
            db, scenario_id=scenario_id, current_user=current_user
        )
        rows = ScenarioTagAssignmentService.assign(
            db,
            scenario_id=scenario_id,
            tag_id=payload.tag_id,
            force=payload.force,
        )
        return [ScenarioTagPublic.model_validate(r) for r in rows]
    except TagAssignmentConflict as e:
        # 409 con el detalle del conflicto para que el frontend pida confirmación
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "tag_assignment_conflict",
                "conflict": ScenarioTagConflictDetail.model_validate(e.detail).model_dump(),
            },
        ) from e
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.delete("/{scenario_id}/tags/{tag_id}", response_model=list[ScenarioTagPublic])
def remove_tag_from_scenario(
    scenario_id: int,
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ScenarioTagPublic]:
    try:
        ScenarioService._require_admin(
            db, scenario_id=scenario_id, current_user=current_user
        )
        rows = ScenarioTagAssignmentService.remove(
            db, scenario_id=scenario_id, tag_id=tag_id
        )
        return [ScenarioTagPublic.model_validate(r) for r in rows]
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
