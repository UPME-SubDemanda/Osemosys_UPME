"""Endpoints REST para ciclo de vida de simulaciones.

Expone: submit (crear job), list (listar jobs del usuario), get (detalle), cancel,
logs (eventos de ejecución), result (artefacto JSON de resultados).
Todos requieren usuario autenticado; delegan a SimulationService.
"""

from __future__ import annotations

import shutil
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
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
from app.simulation.core.data_processing import PARAM_INDEX

router = APIRouter(prefix="/simulations")

_REQUIRED_SET_CSVS = (
    "YEAR.csv",
    "REGION.csv",
    "TECHNOLOGY.csv",
    "TIMESLICE.csv",
    "MODE_OF_OPERATION.csv",
)
_DEMAND_CSV_OPTIONS = ("SpecifiedAnnualDemand.csv", "AccumulatedAnnualDemand.csv")
_ACTIVITY_RATIO_CSV_OPTIONS = ("OutputActivityRatio.csv", "InputActivityRatio.csv")


def _find_csv_root(extract_root: Path) -> Path | None:
    required = set(_REQUIRED_SET_CSVS)
    candidates = [extract_root, *[path for path in extract_root.rglob("*") if path.is_dir()]]
    for candidate in candidates:
        csv_names = {path.name for path in candidate.glob("*.csv")}
        if required.issubset(csv_names):
            return candidate
    return None


def _validate_csv_root(csv_root: Path) -> list[str]:
    csv_names = {path.name for path in csv_root.glob("*.csv")}
    missing_sets = [name for name in _REQUIRED_SET_CSVS if name not in csv_names]
    errors: list[str] = []

    if missing_sets:
        errors.append(
            "Faltan CSV base requeridos: " + ", ".join(missing_sets) + "."
        )

    if not any(name in csv_names for name in _DEMAND_CSV_OPTIONS):
        errors.append(
            "Falta al menos un CSV de demanda: "
            + " o ".join(_DEMAND_CSV_OPTIONS)
            + "."
        )

    if not any(name in csv_names for name in _ACTIVITY_RATIO_CSV_OPTIONS):
        errors.append(
            "Falta al menos un CSV de activity ratio: "
            + " o ".join(_ACTIVITY_RATIO_CSV_OPTIONS)
            + "."
        )

    param_csv_names = {f"{param_name}.csv" for param_name in PARAM_INDEX}
    if not any(name in csv_names for name in param_csv_names):
        errors.append("No se encontraron CSV de parámetros OSeMOSYS reconocidos.")

    return errors


def _extract_zip_to_dir(upload: UploadFile, target_dir: Path) -> None:
    try:
        with zipfile.ZipFile(upload.file) as zf:
            for member in zf.infolist():
                member_path = Path(member.filename)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="El ZIP contiene rutas no válidas.",
                    )
                if member.is_dir():
                    continue
                out_path = target_dir / member_path
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, out_path.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
    except zipfile.BadZipFile as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo cargado no es un ZIP válido.",
        ) from exc


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


@router.post("/from-csv", response_model=SimulationJobPublic, status_code=201)
async def submit_simulation_from_csv(
    csv_zip: UploadFile = File(...),
    solver_name: str = Form("highs"),
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

    settings = get_settings()
    artifact_root = Path(settings.simulation_artifacts_dir).resolve() / "csv_upload_jobs" / str(uuid.uuid4())

    try:
        artifact_root.mkdir(parents=True, exist_ok=True)
        _extract_zip_to_dir(csv_zip, artifact_root)
        csv_root = _find_csv_root(artifact_root)
        if csv_root is None:
            shutil.rmtree(artifact_root, ignore_errors=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "No se encontró un directorio válido con CSV de entrada. "
                    "El ZIP debe contener al menos "
                    + ", ".join(_REQUIRED_SET_CSVS)
                    + "."
                ),
            )
        validation_errors = _validate_csv_root(csv_root)
        if validation_errors:
            shutil.rmtree(artifact_root, ignore_errors=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=" ".join(validation_errors),
            )
        return SimulationService.submit_from_csv(
            db,
            current_user=current_user,
            solver_name=solver_name,
            input_name=csv_zip.filename,
            input_ref=str(csv_root),
        )
    except HTTPException:
        shutil.rmtree(artifact_root, ignore_errors=True)
        raise
    except ConflictError as e:
        shutil.rmtree(artifact_root, ignore_errors=True)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except Exception:
        shutil.rmtree(artifact_root, ignore_errors=True)
        raise


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
