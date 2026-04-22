"""Endpoints REST para ciclo de vida de simulaciones.

Expone: submit (crear job), list (listar jobs del usuario), get (detalle), cancel,
logs (eventos de ejecución), result (artefacto JSON de resultados).
Todos requieren usuario autenticado; delegan a SimulationService.
"""

from __future__ import annotations

import io
import json
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.session import get_db
from app.models import User
from app.schemas.pagination import PaginatedResponse
from app.schemas.simulation import (
    SimulationJobDisplayNamePatch,
    SimulationJobFavoritePatch,
    SimulationJobPublic,
    SimulationLogPublic,
    SimulationOverviewPublic,
    SimulationResultPublic,
    SimulationSubmit,
)
from app.services.csv_scenario_import_service import (
    CsvScenarioImportService,
    extract_zip_to_dir,
    find_csv_root,
    validate_csv_root,
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
            run_iis_analysis=payload.run_iis_analysis,
            display_name=payload.display_name,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.post("/from-csv", response_model=SimulationJobPublic, status_code=201)
async def submit_simulation_from_csv(
    csv_zip: UploadFile = File(...),
    solver_name: str = Form("highs"),
    run_iis_analysis: bool = Form(False),
    input_name: str | None = Form(default=None),
    simulation_type: str = Form(default="NATIONAL"),
    save_as_scenario: bool = Form(default=False),
    scenario_name: str | None = Form(default=None),
    description: str | None = Form(default=None),
    edit_policy: str = Form(default="OWNER_ONLY"),
    tag_id: int | None = Form(default=None),
    display_name: str | None = Form(
        default=None,
        description="Nombre opcional para esta corrida; si se omite, se usa el nombre del archivo ZIP.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Encola una simulación desde un ZIP con CSV procesados."""
    if solver_name not in {"highs", "glpk"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solver inválido. Usa 'highs' o 'glpk'.",
        )
    if not csv_zip.filename or not csv_zip.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes cargar un archivo ZIP con los CSV de entrada.",
        )
    if save_as_scenario and not (scenario_name or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="scenario_name es obligatorio cuando save_as_scenario=true.",
        )
    if edit_policy not in {"OWNER_ONLY", "OPEN", "RESTRICTED"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="edit_policy inválido.",
        )
    settings = get_settings()
    artifact_root = Path(settings.simulation_artifacts_dir).resolve() / "csv_upload_jobs" / str(uuid.uuid4())
    keep_artifacts = False

    try:
        artifact_root.mkdir(parents=True, exist_ok=True)
        extract_zip_to_dir(csv_zip, artifact_root)
        csv_root = find_csv_root(artifact_root)
        if csv_root is None:
            shutil.rmtree(artifact_root, ignore_errors=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "No se encontró un directorio válido con CSV de entrada. "
                    "El ZIP debe contener al menos "
                    + ", ".join(("YEAR.csv", "REGION.csv", "TECHNOLOGY.csv", "TIMESLICE.csv", "MODE_OF_OPERATION.csv"))
                    + "."
                ),
            )
        validation_errors = validate_csv_root(csv_root)
        if validation_errors:
            shutil.rmtree(artifact_root, ignore_errors=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=" ".join(validation_errors),
            )
        if save_as_scenario:
            created_scenario = CsvScenarioImportService.import_from_directory(
                db,
                current_user=current_user,
                csv_root=csv_root,
                scenario_name=(scenario_name or csv_zip.filename or "CSV import"),
                description=description,
                edit_policy=edit_policy,
                tag_id=tag_id,
                simulation_type=simulation_type,
            )
            return SimulationService.submit(
                db,
                current_user=current_user,
                scenario_id=int(created_scenario["id"]),
                solver_name=solver_name,
                display_name=display_name,
            )
        keep_artifacts = True
        return SimulationService.submit_from_csv(
            db,
            current_user=current_user,
            solver_name=solver_name,
            input_name=(input_name or csv_zip.filename or "CSV upload"),
            input_ref=str(csv_root),
            run_iis_analysis=run_iis_analysis,
            simulation_type=simulation_type,
            display_name=display_name,
        )
    except HTTPException:
        raise
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except Exception:
        raise
    finally:
        if not keep_artifacts:
            shutil.rmtree(artifact_root, ignore_errors=True)


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


@router.patch("/{job_id}", response_model=SimulationJobPublic)
def patch_simulation(
    job_id: int,
    payload: SimulationJobDisplayNamePatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Actualiza metadatos editables del job (nombre visible, visibilidad).

    Solo el dueño puede cambiar estos campos. Campos no enviados no se tocan.
    """
    data = payload.model_dump(exclude_unset=True)
    try:
        return SimulationService.patch_metadata(
            db,
            current_user=current_user,
            job_id=job_id,
            display_name=data.get("display_name", ...),
            is_public=data.get("is_public"),
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/{job_id}/favorite", response_model=SimulationJobPublic)
def patch_simulation_favorite(
    job_id: int,
    payload: SimulationJobFavoritePatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Marca/desmarca el resultado como favorito del usuario actual."""
    try:
        return SimulationService.set_favorite(
            db,
            current_user=current_user,
            job_id=job_id,
            favorite=payload.is_favorite,
        )
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


@router.post("/{job_id}/diagnose-infeasibility", response_model=SimulationJobPublic)
def diagnose_infeasibility(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Encola el análisis de infactibilidad (IIS + mapeo a parámetros) para
    un job infactible hecho con HiGHS. Devuelve el job actualizado con
    ``diagnostic_status='QUEUED'``.

    Respuestas:
    - 200: solicitud aceptada; el análisis se ejecuta asincrónicamente.
    - 404: job no encontrado o sin acceso.
    - 409: el job no es infactible, o fue corrido con GLPK (no soporta IIS),
           o el diagnóstico ya está en curso.
    """
    try:
        return SimulationService.request_infeasibility_diagnostic(
            db, current_user=current_user, job_id=job_id
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.post("/{job_id}/cancel-diagnostic", response_model=SimulationJobPublic)
def cancel_infeasibility_diagnostic(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Cancela el análisis de infactibilidad que esté en cola o corriendo
    para el job indicado. Marca la bandera en BD (para que la task
    coopere al siguiente chequeo) y revoca la task en Celery (para
    interrumpir si está atrapada en cálculos largos).

    Respuestas:
    - 200: cancelación aplicada; el job sigue en ``SUCCEEDED`` pero el
           ``diagnostic_status`` pasa a ``FAILED`` con error
           "Cancelado por el usuario".
    - 404: job no encontrado / sin acceso.
    - 409: no hay diagnóstico en cola ni en ejecución (nada para cancelar).
    """
    try:
        return SimulationService.cancel_infeasibility_diagnostic(
            db, current_user=current_user, job_id=job_id
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.get("/{job_id}/infeasibility-report")
def download_infeasibility_report(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Descarga el diagnóstico enriquecido de infactibilidad como JSON.

    Respuestas:
    - 200: archivo JSON (``Content-Disposition: attachment``).
    - 404: job no encontrado o sin diagnóstico disponible.
    """
    try:
        result = SimulationService.get_result(
            db, current_user=current_user, job_id=job_id
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    diagnostics = result.get("infeasibility_diagnostics")
    if not diagnostics:
        raise HTTPException(
            status_code=404,
            detail="El job no tiene diagnóstico de infactibilidad disponible.",
        )

    # Armado del payload descargable: overview y top sospechosos primero, luego
    # IIS, luego detalle. Se EXCLUYE `constraint_violations` (heurística
    # post-solve ruidosa); sigue en BD por compatibilidad interna pero no viaja
    # en el archivo al usuario.
    diag = diagnostics if isinstance(diagnostics, dict) else {}
    cleaned_diagnostics = {
        "overview": diag.get("overview"),
        "iis": diag.get("iis"),
        "top_suspects": diag.get("top_suspects", []),
        "constraint_analyses": diag.get("constraint_analyses", []),
        "var_bound_conflicts": diag.get("var_bound_conflicts", []),
        "unmapped_constraint_prefixes": diag.get("unmapped_constraint_prefixes", []),
        "csv_dir": diag.get("csv_dir"),
    }
    payload = {
        "job_id": result.get("job_id"),
        "scenario_id": result.get("scenario_id"),
        "solver_name": result.get("solver_name"),
        "solver_status": result.get("solver_status"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "infeasibility_diagnostics": cleaned_diagnostics,
    }
    buf = io.BytesIO(json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8"))
    filename = f"infeasibility_report_job_{job_id}.json"
    return StreamingResponse(
        buf,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
