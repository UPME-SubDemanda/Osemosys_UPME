"""Endpoints REST para visualización de resultados de simulaciones.

Provee resúmenes, datos para gráficas individuales y datos para
comparación entre múltiples escenarios.
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.visualization import (
    ChartCatalogItem,
    ChartDataResponse,
    CompareChartFacetResponse,
    CompareChartResponse,
    ResultSummaryResponse,
)
from app.services.simulation_service import SimulationService
from app.visualization import chart_service
from app.core.exceptions import NotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/visualizations")


@router.get("/chart-catalog", response_model=list[ChartCatalogItem])
def get_chart_catalog(
    current_user: User = Depends(get_current_user),
) -> list[ChartCatalogItem]:
    """Catálogo estático de gráficas configuradas en el sistema."""
    return chart_service.get_chart_catalog()


@router.get("/chart-data/compare", response_model=CompareChartResponse)
def get_comparison_data(
    job_ids: str = Query(..., description="Job IDs separados por coma (max 10)"),
    tipo: str = Query(...),
    un: str = Query("PJ"),
    years_to_plot: str = Query("2024,2030,2050", description="Años a plotear separados por coma"),
    agrupacion: str | None = Query(None),
    sub_filtro: str | None = Query(None),
    loc: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Datos para comparación entre múltiples escenarios."""
    job_id_list = []
    try:
        job_id_list = [int(x.strip()) for x in job_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="job_ids inválidos")

    if not job_id_list:
        raise HTTPException(status_code=400, detail="Debe proveer al menos un job_id")
    
    if len(job_id_list) > 10:
        raise HTTPException(status_code=400, detail="Máximo 10 jobs para comparar")

    year_list = []
    try:
        year_list = [int(x.strip()) for x in years_to_plot.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="years_to_plot inválidos")

    # Validar acceso a todos los jobs
    for jid in job_id_list:
        try:
            job = SimulationService.get_by_id(db, current_user=current_user, job_id=jid)
            if job["status"] != "SUCCEEDED":
                raise HTTPException(
                    status_code=400, detail=f"Job {jid} no está en estado SUCCEEDED"
                )
        except NotFoundError:
            raise HTTPException(status_code=404, detail=f"Job {jid} no encontrado o sin acceso")

    try:
        return chart_service.build_comparison_data(
            db=db,
            job_ids=job_id_list,
            tipo=tipo,
            un=un,
            years_to_plot=year_list,
            agrupacion=agrupacion,
            sub_filtro=sub_filtro,
            loc=loc,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/chart-data/compare-facet", response_model=CompareChartFacetResponse)
def get_comparison_facet_data(
    job_ids: str = Query(..., description="Job IDs separados por coma (max 10)"),
    tipo: str = Query(...),
    un: str = Query("PJ"),
    sub_filtro: str | None = Query(None),
    loc: str | None = Query(None),
    variable: str | None = Query(None),
    agrupar_por: str | None = Query(None, description="Override de agrupación: TECNOLOGIA, FUEL, GROUP"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Datos para comparación por escenarios completos (un facet por escenario)."""
    job_id_list = []
    try:
        job_id_list = [int(x.strip()) for x in job_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="job_ids inválidos")

    if not job_id_list:
        raise HTTPException(status_code=400, detail="Debe proveer al menos un job_id")

    if len(job_id_list) > 10:
        raise HTTPException(status_code=400, detail="Máximo 10 jobs para comparar")

    for jid in job_id_list:
        try:
            job = SimulationService.get_by_id(db, current_user=current_user, job_id=jid)
            if job["status"] != "SUCCEEDED":
                raise HTTPException(
                    status_code=400, detail=f"Job {jid} no está en estado SUCCEEDED"
                )
        except NotFoundError:
            raise HTTPException(status_code=404, detail=f"Job {jid} no encontrado o sin acceso")

    try:
        return chart_service.build_comparison_facet_data(
            db=db,
            job_ids=job_id_list,
            tipo=tipo,
            un=un,
            sub_filtro=sub_filtro,
            loc=loc,
            variable=variable,
            agrupar_por=agrupar_por,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{job_id}/result-summary", response_model=ResultSummaryResponse)
def get_result_summary(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """KPIs y resumen general de resultados para un job."""
    try:
        job = SimulationService.get_by_id(db, current_user=current_user, job_id=job_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Job no encontrado o sin acceso")
    
    return chart_service.get_result_summary(db, job_id=job["id"])


@router.get("/{job_id}/chart-data", response_model=ChartDataResponse)
def get_chart_data(
    job_id: int,
    tipo: str = Query(...),
    un: str = Query("PJ"),
    sub_filtro: str | None = Query(None),
    loc: str | None = Query(None),
    variable: str | None = Query(None),
    agrupar_por: str | None = Query(None, description="Override de agrupación: TECNOLOGIA, FUEL, GROUP"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Datos serializados para una gráfica individual."""
    try:
        job = SimulationService.get_by_id(db, current_user=current_user, job_id=job_id)
        if job["status"] != "SUCCEEDED":
            raise HTTPException(status_code=400, detail="Job no está en estado SUCCEEDED")
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Job no encontrado o sin acceso")

    try:
        return chart_service.build_chart_data(
            db=db,
            job_id=job["id"],
            tipo=tipo,
            un=un,
            sub_filtro=sub_filtro,
            loc=loc,
            variable=variable,
            agrupar_por=agrupar_por,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{job_id}/export-all")
def export_all_charts(
    job_id: int,
    un: str = Query("PJ"),
    fmt: str = Query("svg", description="Formato de imagen: svg o png"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Genera un ZIP con todas las gráficas de un escenario como imágenes SVG o PNG."""
    if fmt not in ("svg", "png"):
        raise HTTPException(status_code=400, detail="fmt debe ser 'svg' o 'png'")

    try:
        job = SimulationService.get_by_id(db, current_user=current_user, job_id=job_id)
        if job["status"] != "SUCCEEDED":
            raise HTTPException(status_code=400, detail="Job no está en estado SUCCEEDED")
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Job no encontrado o sin acceso")

    try:
        zip_bytes = chart_service.export_all_charts_zip(
            db=db, job_id=job["id"], un=un, fmt=fmt,
        )
    except Exception as e:
        logger.exception("Error generando ZIP de gráficas")
        raise HTTPException(status_code=500, detail=str(e))

    scenario_name = job.get("scenario_name") or f"Job_{job_id}"
    safe_name = "".join(c if c.isalnum() or c in (" ", "_", "-") else "_" for c in scenario_name)
    filename = f"Graficas_{safe_name}_{un}.zip"

    return StreamingResponse(
        zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@router.get("/{job_id}/export-raw")
def export_raw_data(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Genera un archivo Excel con los datos crudos resultantes de la simulación."""
    try:
        job = SimulationService.get_by_id(db, current_user=current_user, job_id=job_id)
        if job["status"] != "SUCCEEDED":
            raise HTTPException(status_code=400, detail="Job no está en estado SUCCEEDED")
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Job no encontrado o sin acceso")

    try:
        excel_bytes = chart_service.export_raw_data_excel(db=db, job_id=job["id"])
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error generando Excel de datos crudos")
        raise HTTPException(status_code=500, detail=str(e))

    scenario_name = job.get("scenario_name") or f"Job_{job_id}"
    safe_name = "".join(c if c.isalnum() or c in (" ", "_", "-") else "_" for c in scenario_name)
    filename = f"Resultados_Crudos_{safe_name}.xlsx"
    
    return StreamingResponse(
        excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
