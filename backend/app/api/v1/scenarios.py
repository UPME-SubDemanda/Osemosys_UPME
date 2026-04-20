"""Endpoints para escenarios y su matriz de permisos.

CRUD de escenarios, permisos (upsert), valores OSeMOSYS (list, create, update, deactivate),
import desde Excel (create_scenario_from_excel), resumen por año.
"""

from __future__ import annotations

import base64
from pathlib import Path
import shutil
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import zipfile
from io import BytesIO

from app.api.deps import get_current_user
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.session import get_db
from app.models import OsemosysParamValue, Scenario, ScenarioPermission, User
from app.schemas.pagination import PaginatedResponse
from app.schemas.scenario import (
    ApplyExcelChangesRequest,
    OsemosysParamAuditPage,
    OsemosysValuesPage,
    SandIntegrationResponse,
    ScenarioClone,
    ScenarioCreate,
    ScenarioExcelImportResponse,
    ScenarioExcelPreviewResponse,
    ScenarioExcelUpdateResponse,
    ScenarioOsemosysValueCreate,
    ScenarioOsemosysValuePublic,
    ScenarioOsemosysValueUpdate,
    ScenarioOsemosysYearSummary,
    ScenarioPermissionCreate,
    ScenarioPermissionPublic,
    ScenarioPublic,
    ScenarioUpdate,
    VerifySandIntegrationResponse,
)
from app.schemas.scenario_operation import (
    ScenarioCloneAsyncCreate,
    ScenarioOperationJobPublic,
    ScenarioOperationLogPublic,
)
from app.services.scenario_operation_service import ScenarioOperationService
from app.services.integrate_sand_cambios_excel import build_conflictos_workbook_bytes
from app.services.integrate_sand_service import IntegrateSandService
from app.services.official_import_service import OfficialImportService
from app.services.csv_scenario_import_service import (
    CsvScenarioImportService,
    extract_zip_to_dir,
    find_csv_root,
)
from app.core.config import get_settings
from app.services.scenario_export_service import export_scenario_raw_to_excel, export_scenario_to_excel
from app.services.scenario_service import ScenarioService

router = APIRouter(prefix="/scenarios")

@router.get("", response_model=PaginatedResponse[ScenarioPublic])
def list_scenarios(
    busqueda: str | None = None,
    owner: str | None = None,
    edit_policy: str | None = None,
    permission_scope: str | None = None,
    cantidad: int | None = 25,
    offset: int | None = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Lista escenarios accesibles al usuario autenticado.

    Respuestas:
        - 200: listado paginado.
        - 401: autenticación inválida.
    """
    return ScenarioService.list(
        db,
        current_user=current_user,
        busqueda=busqueda,
        owner=owner,
        edit_policy=edit_policy,
        permission_scope=permission_scope,
        cantidad=cantidad,
        offset=offset,
    )


@router.get("/operations", response_model=PaginatedResponse[ScenarioOperationJobPublic])
def list_scenario_operations(
    status_filter: str | None = None,
    operation_type: str | None = None,
    scenario_id: int | None = None,
    cantidad: int | None = 25,
    offset: int | None = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return ScenarioOperationService.list_jobs(
        db,
        current_user=current_user,
        status=status_filter,
        operation_type=operation_type,
        scenario_id=scenario_id,
        cantidad=cantidad,
        offset=offset,
    )


@router.get("/operations/{job_id}", response_model=ScenarioOperationJobPublic)
def get_scenario_operation(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        return ScenarioOperationService.get_by_id(db, current_user=current_user, job_id=job_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/operations/{job_id}/logs", response_model=PaginatedResponse[ScenarioOperationLogPublic])
def get_scenario_operation_logs(
    job_id: int,
    cantidad: int | None = 50,
    offset: int | None = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        return ScenarioOperationService.list_logs(
            db,
            current_user=current_user,
            job_id=job_id,
            cantidad=cantidad,
            offset=offset,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("", response_model=ScenarioPublic, status_code=201)
def create_scenario(
    payload: ScenarioCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Crea escenario y aplica reglas de ownership/política de edición.

    Método HTTP:
        - `POST` por creación de recurso.
    """
    try:
        return ScenarioService.create(
            db,
            current_user=current_user,
            name=payload.name,
            description=payload.description,
            edit_policy=payload.edit_policy,
            is_template=payload.is_template,
            tag_id=payload.tag_id,
            simulation_type=payload.simulation_type,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.post("/import-excel", response_model=ScenarioExcelImportResponse, status_code=201)
def create_scenario_from_excel(
    file: UploadFile = File(...),
    sheet_name: str = Form(...),
    scenario_name: str = Form(...),
    description: str | None = Form(default=None),
    edit_policy: str = Form(default="OWNER_ONLY"),
    tag_id: int | None = Form(default=None),
    simulation_type: str = Form(default="NATIONAL"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Crea un escenario y carga datos desde Excel (sincrónico)."""
    if edit_policy not in {"OWNER_ONLY", "OPEN", "RESTRICTED"}:
        raise HTTPException(status_code=422, detail="edit_policy inválido.")
    if not scenario_name.strip():
        raise HTTPException(status_code=422, detail="El nombre del escenario es obligatorio.")
    if not sheet_name.strip():
        raise HTTPException(status_code=422, detail="La hoja es obligatoria.")
    filename = file.filename or "import.xlsx"
    content = file.file.read()
    if not content:
        raise HTTPException(status_code=422, detail="El archivo está vacío.")

    try:
        created = ScenarioService.create(
            db,
            current_user=current_user,
            name=scenario_name.strip(),
            description=(description.strip() if description else None),
            edit_policy=edit_policy,  # type: ignore[arg-type]
            is_template=False,
            simulation_type=simulation_type,
            skip_populate_defaults=True,
            tag_id=tag_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    sid = int(created["id"])

    try:
        import_dict = OfficialImportService.import_xlsm(
            db,
            filename=filename,
            content=content,
            imported_by=current_user.username,
            selected_sheet_name=sheet_name,
            scenario_id_override=sid,
        )
        ScenarioService.sync_catalogs_from_scenario_values(db, scenario_id=sid)
        ScenarioService.ensure_default_reserve_margin_udc(db, scenario_id=sid)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        scenario_public = ScenarioService.get_public(db, scenario_id=sid, current_user=current_user)
    except (NotFoundError, ForbiddenError, ConflictError):
        scenario_public = created

    return {"scenario": scenario_public, "import_result": import_dict}


@router.post("/import-csv", response_model=ScenarioPublic, status_code=201)
def create_scenario_from_csv(
    csv_zip: UploadFile = File(...),
    scenario_name: str = Form(...),
    description: str | None = Form(default=None),
    edit_policy: str = Form(default="OWNER_ONLY"),
    tag_id: int | None = Form(default=None),
    simulation_type: str = Form(default="NATIONAL"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Crea un escenario a partir de un ZIP con CSV OSeMOSYS procesados."""
    if edit_policy not in {"OWNER_ONLY", "OPEN", "RESTRICTED"}:
        raise HTTPException(status_code=422, detail="edit_policy inválido.")
    if not scenario_name.strip():
        raise HTTPException(status_code=422, detail="El nombre del escenario es obligatorio.")
    if not csv_zip.filename or not csv_zip.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=422, detail="Debes cargar un archivo ZIP válido.")

    settings = get_settings()
    artifact_root = (
        Path(settings.simulation_artifacts_dir).resolve() / "csv_scenario_imports" / str(uuid.uuid4())
    )

    try:
        artifact_root.mkdir(parents=True, exist_ok=True)
        extract_zip_to_dir(csv_zip, artifact_root)
        csv_root = find_csv_root(artifact_root)
        if csv_root is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No se encontró un directorio válido con CSV de entrada. "
                    "El ZIP debe contener al menos YEAR.csv, REGION.csv, TECHNOLOGY.csv, "
                    "TIMESLICE.csv y MODE_OF_OPERATION.csv."
                ),
            )
        return CsvScenarioImportService.import_from_directory(
            db,
            current_user=current_user,
            csv_root=csv_root,
            scenario_name=scenario_name,
            description=description,
            edit_policy=edit_policy,
            tag_id=tag_id,
            simulation_type=simulation_type,
        )
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        shutil.rmtree(artifact_root, ignore_errors=True)


def _form_bool_flag(value: str | None) -> bool:
    if value is None or value == "":
        return False
    return value.strip().lower() in ("1", "true", "yes", "on")


@router.post("/concatenate-sand")
def concatenate_sand_files(
    base_file: UploadFile = File(...),
    new_files: list[UploadFile] = File(...),
    drop_techs: str | None = Form(default=None),
    drop_fuels: str | None = Form(default=None),
    include_log_txt: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Concatena/integra múltiples archivos SAND y devuelve un Excel integrado (o ZIP con Excel + log)."""
    _ = db
    _ = current_user

    want_log_zip = _form_bool_flag(include_log_txt)

    base_filename = base_file.filename or "base.xlsx"
    base_content = base_file.file.read()

    collected_new_files: list[tuple[str, bytes]] = []
    for upload in new_files:
        filename = upload.filename or "nuevo.xlsx"
        content = upload.file.read()
        collected_new_files.append((filename, content))

    try:
        result = IntegrateSandService.integrate_sand_files(
            base_filename=base_filename,
            base_content=base_content,
            new_files=collected_new_files,
            drop_techs_csv=drop_techs,
            drop_fuels_csv=drop_fuels,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Ocurrió un error inesperado durante la integración SAND.",
        ) from exc

    log_text = result.get("log_text") or ""
    log_line_count = len(log_text.splitlines()) if log_text else 0
    integration_failed = bool(result.get("integration_failed"))
    conflictos_n = int(result.get("conflictos_count", 0))
    has_conflicts_success = not integration_failed and conflictos_n > 0

    ev_raw = result.get("export_verification")
    summary_obj = SandIntegrationResponse.model_validate(
        {
            "total_filas": result["total_filas"],
            "contribuciones": result["contribuciones"],
            "conflictos_count": conflictos_n,
            "conflictos": jsonable_encoder(result.get("conflictos", [])),
            "resumen": result["resumen"],
            "warnings": result["warnings"],
            "errors": result.get("errors", []),
            "has_log": bool(log_text.strip())
            and (want_log_zip or integration_failed or has_conflicts_success),
            "log_line_count": log_line_count,
            "has_cambios_xlsx": want_log_zip
            and bool((result.get("cambios_excel_content") or b""))
            and not integration_failed
            and not has_conflicts_success,
            "has_conflictos_xlsx": has_conflicts_success,
            "integration_failed": integration_failed,
            "export_verification": jsonable_encoder(ev_raw) if ev_raw is not None else None,
        }
    )
    summary_json = summary_obj.model_dump_json()
    summary_header = base64.urlsafe_b64encode(summary_json.encode("utf-8")).decode("ascii")
    output_filename = result["output_filename"]

    if integration_failed:
        if want_log_zip:
            zip_buf = BytesIO()
            stem = Path(base_filename).stem
            zip_name = f"{stem}_integracion_error.zip"
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("integracion_sand_log.txt", log_text.encode("utf-8"))
            zip_buf.seek(0)
            return StreamingResponse(
                zip_buf,
                media_type="application/zip",
                headers={
                    "Content-Disposition": f'attachment; filename="{zip_name}"',
                    "X-Sand-Integration-Summary": summary_header,
                    "X-Sand-Integration-Summary-Format": "base64-json",
                },
            )
        return StreamingResponse(
            BytesIO(log_text.encode("utf-8")),
            media_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="integracion_sand_log.txt"',
                "X-Sand-Integration-Summary": summary_header,
                "X-Sand-Integration-Summary-Format": "base64-json",
            },
        )

    if has_conflicts_success:
        conf_xlsx = build_conflictos_workbook_bytes(list(result.get("conflictos") or []))
        zip_buf = BytesIO()
        stem = Path(output_filename).stem
        zip_name = f"{stem}_conflictos.zip"
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("integracion_sand_log.txt", log_text.encode("utf-8"))
            zf.writestr("conflictos_integracion.xlsx", conf_xlsx)
        zip_buf.seek(0)
        return StreamingResponse(
            zip_buf,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{zip_name}"',
                "X-Sand-Integration-Summary": summary_header,
                "X-Sand-Integration-Summary-Format": "base64-json",
            },
        )

    if want_log_zip:
        zip_buf = BytesIO()
        stem = Path(output_filename).stem
        zip_name = f"{stem}_con_log.zip"
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(output_filename, result["output_content"])
            zf.writestr("integracion_sand_log.txt", log_text.encode("utf-8"))
            cambios = result.get("cambios_excel_content") or b""
            if cambios:
                zf.writestr("cambios_integracion.xlsx", cambios)
        zip_buf.seek(0)
        return StreamingResponse(
            zip_buf,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{zip_name}"',
                "X-Sand-Integration-Summary": summary_header,
                "X-Sand-Integration-Summary-Format": "base64-json",
            },
        )

    return StreamingResponse(
        BytesIO(result["output_content"]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{output_filename}"',
            "X-Sand-Integration-Summary": summary_header,
            "X-Sand-Integration-Summary-Format": "base64-json",
        },
    )


@router.post("/verify-sand-integration", response_model=VerifySandIntegrationResponse)
def verify_sand_integration(
    base_file: UploadFile = File(...),
    integrated_file: UploadFile = File(...),
    new_files: list[UploadFile] = File(...),
    drop_techs: str | None = Form(default=None),
    drop_fuels: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Verifica un Excel integrado respecto a la base y los archivos nuevos (misma lógica que la doble verificación)."""
    _ = db
    _ = current_user

    base_filename = base_file.filename or "base.xlsx"
    base_content = base_file.file.read()
    integrated_filename = integrated_file.filename or "integrado.xlsx"
    integrated_content = integrated_file.file.read()

    collected_new_files: list[tuple[str, bytes]] = []
    for upload in new_files:
        filename = upload.filename or "nuevo.xlsx"
        content = upload.file.read()
        collected_new_files.append((filename, content))

    try:
        result = IntegrateSandService.verify_integrated_export_standalone(
            base_filename=base_filename,
            base_content=base_content,
            integrated_filename=integrated_filename,
            integrated_content=integrated_content,
            new_files=collected_new_files,
            drop_techs_csv=drop_techs,
            drop_fuels_csv=drop_fuels,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Ocurrió un error inesperado durante la verificación SAND.",
        )

    ev_raw = result["export_verification"]
    return VerifySandIntegrationResponse.model_validate(
        {
            "standalone": True,
            "export_verification": jsonable_encoder(ev_raw),
        }
    )


@router.get("/{scenario_id}", response_model=ScenarioPublic)
def get_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Obtiene un escenario individual si el usuario tiene visibilidad."""
    try:
        return ScenarioService.get_public(db, scenario_id=scenario_id, current_user=current_user)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e


@router.get("/{scenario_id}/export-excel")
def export_scenario_excel(
    scenario_id: int,
    export_format: str = Query(default="sand", alias="format"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Descarga el escenario en Excel: `sand` (default) o `raw`."""
    try:
        scenario_dict = ScenarioService.get_public(
            db, scenario_id=scenario_id, current_user=current_user
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e

    scenario_name = scenario_dict.get("name", "scenario")
    normalized_format = (export_format or "sand").strip().lower()
    if normalized_format not in {"sand", "raw"}:
        raise HTTPException(status_code=422, detail="Formato inválido. Usa 'sand' o 'raw'.")
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in scenario_name).strip() or "scenario"
    filename = (
        f"{safe_name}_Parameters_RAW.xlsx"
        if normalized_format == "raw"
        else f"{safe_name}_Parameters_SAND.xlsx"
    )

    content = (
        export_scenario_raw_to_excel(db, scenario_id=scenario_id, scenario_name=scenario_name)
        if normalized_format == "raw"
        else export_scenario_to_excel(db, scenario_id=scenario_id, scenario_name=scenario_name)
    )
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/{scenario_id}", response_model=ScenarioPublic)
def update_scenario(
    scenario_id: int,
    payload: ScenarioUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Actualiza metadatos de escenario y registra auditoría."""
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=422, detail="No hay campos para actualizar.")
    try:
        return ScenarioService.update_metadata(
            db,
            scenario_id=scenario_id,
            current_user=current_user,
            payload=data,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.delete("/{scenario_id}", status_code=204)
def delete_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Elimina un escenario y todos sus datos asociados. Solo el propietario puede eliminarlo."""
    scenario = db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Escenario no encontrado.")
    if scenario.owner != current_user.username:
        raise HTTPException(status_code=403, detail="Solo el propietario puede eliminar el escenario.")

    db.query(OsemosysParamValue).filter(OsemosysParamValue.id_scenario == scenario_id).delete()
    db.query(ScenarioPermission).filter(ScenarioPermission.id_scenario == scenario_id).delete()
    db.delete(scenario)
    db.commit()


@router.post("/{scenario_id}/clone", response_model=ScenarioPublic, status_code=201)
def clone_scenario(
    scenario_id: int,
    payload: ScenarioClone,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Scenario:
    """Clona un escenario con todos sus datos OSeMOSYS.

    El usuario debe tener acceso al escenario origen.
    El nuevo escenario pertenece al usuario que realiza la copia.
    """
    try:
        return ScenarioService.clone(
            db,
            source_scenario_id=scenario_id,
            current_user=current_user,
            name=payload.name,
            description=payload.description,
            edit_policy=payload.edit_policy,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.post("/{scenario_id}/clone-async", response_model=ScenarioOperationJobPublic, status_code=202)
def clone_scenario_async(
    scenario_id: int,
    payload: ScenarioCloneAsyncCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        return ScenarioOperationService.submit_clone(
            db,
            scenario_id=scenario_id,
            current_user=current_user,
            name=payload.name,
            description=payload.description,
            edit_policy=payload.edit_policy,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.post(
    "/{scenario_id}/update-from-excel",
    response_model=ScenarioExcelUpdateResponse,
    status_code=200,
)
def update_scenario_from_excel(
    scenario_id: int,
    file: UploadFile = File(...),
    sheet_name: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Actualiza valores existentes de un escenario desde un Excel SAND.

    Solo modifica registros que ya existen (clave compuesta). Los registros
    del Excel sin coincidencia se reportan como advertencias sin insertar.
    La operación es transaccional.
    """
    scenario = db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Escenario no encontrado.")
    try:
        ScenarioService._require_manage_values(db, scenario_id=scenario_id, current_user=current_user)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e

    if not sheet_name.strip():
        raise HTTPException(status_code=422, detail="La hoja es obligatoria.")
    filename = file.filename or "update.xlsx"
    content = file.file.read()
    if not content:
        raise HTTPException(status_code=422, detail="El archivo está vacío.")

    try:
        preview = OfficialImportService.preview_scenario_from_excel(
            db,
            scenario_id=scenario_id,
            filename=filename,
            content=content,
            selected_sheet_name=sheet_name,
        )
        result = OfficialImportService.update_scenario_from_excel(
            db,
            scenario_id=scenario_id,
            filename=filename,
            content=content,
            selected_sheet_name=sheet_name,
        )
        ScenarioService.sync_catalogs_from_scenario_values(db, scenario_id=scenario_id)
        changed_param_names = sorted({row["param_name"] for row in preview["changes"]})
        ScenarioService._track_changed_params(scenario, param_names=changed_param_names)
        if changed_param_names:
            db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return result


@router.post(
    "/{scenario_id}/preview-from-excel",
    response_model=ScenarioExcelPreviewResponse,
    status_code=200,
)
def preview_scenario_from_excel(
    scenario_id: int,
    file: UploadFile = File(...),
    sheet_name: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Genera preview de cambios desde un Excel SAND sin modificar datos.

    Retorna la lista de diferencias (valor actual vs nuevo) para que
    el usuario revise y confirme antes de aplicar.
    """
    scenario = db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Escenario no encontrado.")
    try:
        ScenarioService._require_manage_values(db, scenario_id=scenario_id, current_user=current_user)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e

    if not sheet_name.strip():
        raise HTTPException(status_code=422, detail="La hoja es obligatoria.")
    filename = file.filename or "preview.xlsx"
    content = file.file.read()
    if not content:
        raise HTTPException(status_code=422, detail="El archivo está vacío.")

    try:
        return OfficialImportService.preview_scenario_from_excel(
            db,
            scenario_id=scenario_id,
            filename=filename,
            content=content,
            selected_sheet_name=sheet_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/{scenario_id}/apply-excel-changes",
    response_model=ScenarioExcelUpdateResponse,
    status_code=200,
)
def apply_excel_changes(
    scenario_id: int,
    payload: ApplyExcelChangesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Aplica cambios confirmados por el usuario tras un preview.

    Recibe la lista de (row_id, new_value) seleccionados por el usuario.
    Solo actualiza filas que pertenecen al escenario indicado.
    """
    scenario = db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Escenario no encontrado.")
    try:
        ScenarioService._require_manage_values(db, scenario_id=scenario_id, current_user=current_user)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e

    result = OfficialImportService.apply_excel_changes(
        db,
        scenario_id=scenario_id,
        changes=[c.model_dump() for c in payload.changes],
    )
    ScenarioService.sync_catalogs_from_scenario_values(db, scenario_id=scenario_id)
    changed_param_names = sorted(
        {
            str(c.param_name).strip()
            for c in payload.changes
            if c.param_name is not None and str(c.param_name).strip()
        }
    )
    update_ids = [int(c.row_id) for c in payload.changes if c.row_id is not None]
    if update_ids:
        changed_param_names.extend(
            sorted(
                {
                    row.param_name
                    for row in db.query(OsemosysParamValue)
                    .filter(
                        OsemosysParamValue.id_scenario == scenario_id,
                        OsemosysParamValue.id.in_(update_ids),
                    )
                    .all()
                }
            )
        )
        changed_param_names = sorted({name for name in changed_param_names if name})
    ScenarioService._track_changed_params(scenario, param_names=changed_param_names)
    if changed_param_names:
        db.commit()

    return {
        "updated": result["updated"],
        "inserted": result.get("inserted", 0),
        "skipped": result["skipped"],
        "not_found": 0,
        "total_rows_read": len(payload.changes),
        "warnings": [],
    }


@router.post(
    "/{scenario_id}/apply-excel-changes-async",
    response_model=ScenarioOperationJobPublic,
    status_code=202,
)
def apply_excel_changes_async(
    scenario_id: int,
    payload: ApplyExcelChangesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        return ScenarioOperationService.submit_apply_excel_changes(
            db,
            scenario_id=scenario_id,
            current_user=current_user,
            changes=[c.model_dump() for c in payload.changes],
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.get("/{scenario_id}/permissions", response_model=list[ScenarioPermissionPublic])
def list_permissions(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ScenarioPermission]:
    """Lista permisos efectivos configurados para un escenario.

    Seguridad:
        - restringido a usuarios con acceso al escenario.
    """
    try:
        return ScenarioService.list_permissions(db, scenario_id=scenario_id, current_user=current_user)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e


@router.get("/{scenario_id}/osemosys-summary", response_model=list[ScenarioOsemosysYearSummary])
def list_osemosys_summary(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Lista resumen por parámetro/año de valores OSeMOSYS de un escenario."""
    try:
        return ScenarioService.list_osemosys_summary(
            db, scenario_id=scenario_id, current_user=current_user
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e


@router.get("/{scenario_id}/osemosys-param-audit", response_model=OsemosysParamAuditPage)
def list_osemosys_param_audit(
    scenario_id: int,
    param_name: str = Query(..., min_length=1, max_length=128),
    offset: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Historial de cambios (auditoría) para un parámetro OSeMOSYS del escenario."""
    try:
        return ScenarioService.list_osemosys_param_audit(
            db,
            scenario_id=scenario_id,
            current_user=current_user,
            param_name=param_name,
            offset=offset,
            limit=limit,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e


@router.get("/{scenario_id}/osemosys-values", response_model=OsemosysValuesPage)
def list_osemosys_values(
    scenario_id: int,
    param_name: str | None = None,
    param_name_exact: bool = False,
    year: int | None = None,
    search: str | None = None,
    offset: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Paginación server-side de valores OSeMOSYS con búsqueda global."""
    try:
        return ScenarioService.list_osemosys_values(
            db,
            scenario_id=scenario_id,
            current_user=current_user,
            param_name=param_name,
            param_name_exact=param_name_exact,
            year=year,
            search=search,
            offset=offset,
            limit=limit,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e


@router.post("/{scenario_id}/osemosys-values", response_model=ScenarioOsemosysValuePublic, status_code=201)
def create_osemosys_value(
    scenario_id: int,
    payload: ScenarioOsemosysValueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Crea un valor OSeMOSYS específico para el escenario."""
    try:
        return ScenarioService.create_osemosys_value(
            db,
            scenario_id=scenario_id,
            current_user=current_user,
            payload=payload.model_dump(),
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.put("/{scenario_id}/osemosys-values/{value_id}", response_model=ScenarioOsemosysValuePublic)
def update_osemosys_value(
    scenario_id: int,
    value_id: int,
    payload: ScenarioOsemosysValueUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Actualiza un valor OSeMOSYS del escenario."""
    try:
        return ScenarioService.update_osemosys_value(
            db,
            scenario_id=scenario_id,
            value_id=value_id,
            current_user=current_user,
            payload=payload.model_dump(),
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.delete("/{scenario_id}/osemosys-values/{value_id}")
def deactivate_osemosys_value(
    scenario_id: int,
    value_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Desactiva un valor OSeMOSYS (eliminación del escenario)."""
    try:
        ScenarioService.deactivate_osemosys_value(
            db,
            scenario_id=scenario_id,
            value_id=value_id,
            current_user=current_user,
        )
        return {"status": "deactivated"}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e


@router.post("/{scenario_id}/permissions", response_model=ScenarioPermissionPublic, status_code=201)
def upsert_permission(
    scenario_id: int,
    payload: ScenarioPermissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScenarioPermission:
    """Crea o actualiza permiso de un usuario sobre un escenario.

    Método HTTP:
        - `POST` porque actúa como upsert de acción de dominio.
    """
    try:
        return ScenarioService.upsert_permission(
            db,
            scenario_id=scenario_id,
            current_user=current_user,
            user_id=payload.user_id,
            user_identifier=payload.user_identifier,
            can_edit_direct=payload.can_edit_direct,
            can_propose=payload.can_propose,
            can_manage_values=payload.can_manage_values,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


# ---------------------------------------------------------------------------
#  UDC Config (celda 20 del notebook)
# ---------------------------------------------------------------------------

@router.get("/{scenario_id}/udc-config")
def get_udc_config(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Devuelve la configuración UDC del escenario."""
    scenario = db.get(Scenario, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Escenario no encontrado")

    default_config = {
        "enabled": False,
        "multipliers": [],
        "tag_value": 0,
    }
    if scenario.udc_config is None:
        return default_config
    cfg = dict(scenario.udc_config)
    cfg.setdefault("enabled", True)   # backward compat: configs sin campo → activos
    cfg.setdefault("multipliers", [])
    cfg.setdefault("tag_value", 0)
    return cfg


@router.put("/{scenario_id}/udc-config")
def update_udc_config(
    scenario_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Actualiza la configuración UDC del escenario.

    Payload esperado:
    {
        "multipliers": [
            {"type": "TotalCapacity", "tech_dict": {"TECH_A": -1.0, ...}},
            {"type": "NewCapacity", "tech_dict": {...}},
        ],
        "tag_value": 0
    }
    """
    scenario = db.get(Scenario, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Escenario no encontrado")

    enabled = payload.get("enabled", True)
    if not enabled:
        scenario.udc_config = None
        db.commit()
        return {"enabled": False, "multipliers": [], "tag_value": 0}

    multipliers = payload.get("multipliers", [])
    valid_types = {"TotalCapacity", "NewCapacity", "Activity"}
    for m in multipliers:
        if m.get("type") not in valid_types:
            raise HTTPException(
                status_code=422,
                detail=f"multiplier type debe ser uno de {valid_types}",
            )
        if not isinstance(m.get("tech_dict"), dict):
            raise HTTPException(
                status_code=422,
                detail="tech_dict debe ser un diccionario {TECHNOLOGY: valor}",
            )

    tag_value = payload.get("tag_value")
    if tag_value is not None and tag_value not in (0, 1):
        raise HTTPException(status_code=422, detail="tag_value debe ser 0 o 1")

    scenario.udc_config = {**payload, "enabled": True}
    db.commit()
    cfg = dict(scenario.udc_config)
    cfg.setdefault("multipliers", [])
    cfg.setdefault("tag_value", 0)
    return cfg


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Exponer gestión de escenarios y control de acceso colaborativo.
#
# Posibles mejoras:
# - Separar endpoints de lectura y administración en routers distintos por rol.
#
# Riesgos en producción:
# - Errores en políticas de edición pueden permitir cambios no autorizados.
#
# Escalabilidad:
# - Coste principal en consultas de permisos y paginación de escenarios.
