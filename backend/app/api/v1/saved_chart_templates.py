"""Endpoints REST para plantillas de gráficas guardadas y generación de reportes.

Las plantillas están scope-by-user: cada usuario solo ve y gestiona las suyas.
"""

from __future__ import annotations

import io
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.session import get_db
from app.models import User
from app.schemas.saved_chart_template import (
    ReportRequest,
    ReportSavedCreate,
    ReportSavedPublic,
    ReportSavedUpdate,
    SavedChartTemplateCreate,
    SavedChartTemplatePublic,
    SavedChartTemplateUpdate,
)
from app.services.saved_chart_template_service import (
    ReportTemplateService,
    SavedChartTemplateService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/saved-chart-templates")


@router.get("", response_model=list[SavedChartTemplatePublic])
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SavedChartTemplatePublic]:
    rows = SavedChartTemplateService.list_accessible(
        db, user_id=current_user.id
    )
    return [SavedChartTemplatePublic.model_validate(r) for r in rows]


@router.post("", response_model=SavedChartTemplatePublic, status_code=201)
def create_template(
    payload: SavedChartTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedChartTemplatePublic:
    data = SavedChartTemplateService.create(
        db,
        user_id=current_user.id,
        payload=payload.model_dump(),
    )
    return SavedChartTemplatePublic.model_validate(data)


@router.get("/{template_id}", response_model=SavedChartTemplatePublic)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedChartTemplatePublic:
    try:
        obj, owner = SavedChartTemplateService.get_accessible(
            db, user_id=current_user.id, template_id=template_id
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    from app.services.saved_chart_template_service import _chart_to_public_dict

    return SavedChartTemplatePublic.model_validate(
        _chart_to_public_dict(
            obj, current_user_id=current_user.id, owner_username=owner
        )
    )


@router.patch("/{template_id}", response_model=SavedChartTemplatePublic)
def update_template(
    template_id: int,
    payload: SavedChartTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedChartTemplatePublic:
    data = payload.model_dump(exclude_unset=True)
    try:
        row = SavedChartTemplateService.update(
            db,
            user_id=current_user.id,
            template_id=template_id,
            name=data.get("name"),
            description=data.get("description"),
            is_public=data.get("is_public"),
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return SavedChartTemplatePublic.model_validate(row)


@router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    try:
        SavedChartTemplateService.delete(
            db, user_id=current_user.id, template_id=template_id
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/report")
def generate_report(
    payload: ReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Genera un ZIP con las plantillas solicitadas y sus escenarios asignados.

    Dos modos:
      - Plano: envía ``items`` (lista plana ordenada).
      - Estructurado: envía ``organize_by_category=True`` y ``categories``
        (árbol categoría → subcategoría → items). El ZIP queda organizado en
        carpetas ``01_Categoria/[01_Sub/]nn_nombre.ext``.
    """
    try:
        buffer, filename = SavedChartTemplateService.generate_report_zip(
            db,
            current_user=current_user,
            items=payload.items,
            fmt=payload.fmt,
            organize_by_category=payload.organize_by_category,
            categories=payload.categories,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        ) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # pragma: no cover — guard de último recurso
        logger.exception("Error generando reporte")
        raise HTTPException(status_code=500, detail=str(e)) from e

    return StreamingResponse(
        io.BytesIO(buffer.getvalue()),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Reportes guardados (colecciones de plantillas con nombre / descripción)
# ---------------------------------------------------------------------------


reports_router = APIRouter(prefix="/saved-reports")


@reports_router.get("", response_model=list[ReportSavedPublic])
def list_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ReportSavedPublic]:
    rows = ReportTemplateService.list_accessible(
        db, user_id=current_user.id
    )
    return [ReportSavedPublic.model_validate(r) for r in rows]


@reports_router.post("", response_model=ReportSavedPublic, status_code=201)
def create_report(
    payload: ReportSavedCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReportSavedPublic:
    try:
        row = ReportTemplateService.create(
            db,
            current_user=current_user,
            name=payload.name,
            description=payload.description,
            fmt=payload.fmt,
            items=payload.items,
            layout=(
                payload.layout.model_dump() if payload.layout is not None else None
            ),
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ReportSavedPublic.model_validate(row)


@reports_router.get("/{report_id}", response_model=ReportSavedPublic)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReportSavedPublic:
    try:
        obj, owner = ReportTemplateService.get_accessible(
            db, user_id=current_user.id, report_id=report_id
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    from app.services.saved_chart_template_service import _report_to_public_dict

    return ReportSavedPublic.model_validate(
        _report_to_public_dict(
            obj, current_user_id=current_user.id, owner_username=owner
        )
    )


@reports_router.patch("/{report_id}", response_model=ReportSavedPublic)
def update_report(
    report_id: int,
    payload: ReportSavedUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReportSavedPublic:
    data = payload.model_dump(exclude_unset=True)
    # ``layout`` es tri-valente: ausente = no tocar, ``None`` = resetear a auto,
    # dict = override. Usamos ``...`` como sentinel interno del service.
    layout_arg: object = ...
    if "layout" in data:
        layout_arg = data["layout"]
    try:
        row = ReportTemplateService.update(
            db,
            current_user=current_user,
            report_id=report_id,
            name=data.get("name"),
            description=data.get("description", ...),
            fmt=data.get("fmt"),
            items=data.get("items"),
            is_public=data.get("is_public"),
            is_official=data.get("is_official"),
            layout=layout_arg,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ReportSavedPublic.model_validate(row)


@reports_router.delete("/{report_id}", status_code=204)
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    try:
        ReportTemplateService.delete(
            db, current_user=current_user, report_id=report_id
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
