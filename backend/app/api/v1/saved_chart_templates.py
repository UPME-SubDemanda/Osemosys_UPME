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
    SavedFavoritePatch,
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
        db, user_id=current_user.id, current_user=current_user
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
            db,
            user_id=current_user.id,
            template_id=template_id,
            current_user=current_user,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    from app.services.saved_chart_template_service import (
        _chart_to_public_dict,
        _load_chart_favorite_ids,
    )

    fav_ids = _load_chart_favorite_ids(db, user_id=current_user.id)
    return SavedChartTemplatePublic.model_validate(
        _chart_to_public_dict(
            obj,
            current_user_id=current_user.id,
            owner_username=owner,
            is_favorite=int(obj.id) in fav_ids,
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
            current_user=current_user,
            template_id=template_id,
            data=data,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        ) from e
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
            job_display_overrides=payload.job_display_overrides,
            year_from=payload.year_from,
            year_to=payload.year_to,
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
    include_others_private: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ReportSavedPublic]:
    rows = ReportTemplateService.list_accessible(
        db,
        current_user=current_user,
        include_others_private=include_others_private,
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
            scenario_aliases=payload.scenario_aliases,
            default_job_ids=payload.default_job_ids,
            year_from=payload.year_from,
            year_to=payload.year_to,
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
            db, current_user=current_user, report_id=report_id
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    from app.services.saved_chart_template_service import (
        _load_report_favorite_ids,
        _report_to_public_dict,
    )

    fav_ids = _load_report_favorite_ids(db, user_id=current_user.id)
    return ReportSavedPublic.model_validate(
        _report_to_public_dict(
            obj,
            current_user_id=current_user.id,
            owner_username=owner,
            is_favorite=int(obj.id) in fav_ids,
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
    # ``layout`` y ``scenario_aliases`` son tri-valentes: ausente = no tocar,
    # ``None`` = resetear, valor = override. Usamos ``...`` como sentinel.
    layout_arg: object = ...
    if "layout" in data:
        layout_arg = data["layout"]
    aliases_arg: object = ...
    if "scenario_aliases" in data:
        aliases_arg = data["scenario_aliases"]
    defaults_arg: object = ...
    if "default_job_ids" in data:
        defaults_arg = data["default_job_ids"]
    year_from_arg: object = ...
    if "year_from" in data:
        year_from_arg = data["year_from"]
    year_to_arg: object = ...
    if "year_to" in data:
        year_to_arg = data["year_to"]
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
            scenario_aliases=aliases_arg,
            default_job_ids=defaults_arg,
            year_from=year_from_arg,
            year_to=year_to_arg,
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
    except ForbiddenError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        ) from e


# ─── Favoritos y Copy ───────────────────────────────────────────────────────


@reports_router.patch("/{report_id}/favorite", response_model=ReportSavedPublic)
def set_report_favorite(
    report_id: int,
    payload: SavedFavoritePatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReportSavedPublic:
    try:
        row = ReportTemplateService.set_favorite(
            db,
            current_user=current_user,
            report_id=report_id,
            is_favorite=payload.is_favorite,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return ReportSavedPublic.model_validate(row)


@reports_router.post(
    "/{report_id}/copy", response_model=ReportSavedPublic, status_code=201
)
def copy_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReportSavedPublic:
    """Crea una copia privada del reporte para el usuario actual.

    Para las plantillas de gráfica referenciadas que no sean accesibles al
    usuario (p. ej. privadas de otro usuario), se clonan como plantillas
    privadas del caller y se actualizan las referencias.
    """
    try:
        row = ReportTemplateService.copy_report(
            db, current_user=current_user, report_id=report_id
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return ReportSavedPublic.model_validate(row)


@router.patch("/{template_id}/favorite", response_model=SavedChartTemplatePublic)
def set_chart_favorite(
    template_id: int,
    payload: SavedFavoritePatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedChartTemplatePublic:
    try:
        row = SavedChartTemplateService.set_favorite(
            db,
            user_id=current_user.id,
            template_id=template_id,
            is_favorite=payload.is_favorite,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return SavedChartTemplatePublic.model_validate(row)
