"""Endpoints para importación de datos oficiales desde Excel (.xlsm/.xlsx).

Expone:
  - POST /xlsm/sheets: inspecciona hojas del workbook sin importar.
  - POST /xlsm: importa datos al escenario de defecto (requiere permiso can_import_official_data).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_official_data_import_manager
from app.models import User
from app.schemas.official_import import OfficialWorkbookSheets
from app.services.official_import_service import OfficialImportService

router = APIRouter(prefix="/official-import")


@router.post("/xlsm/sheets", response_model=OfficialWorkbookSheets)
def inspect_official_xlsm_sheets(
    file: UploadFile = File(...),
    _: User = Depends(get_official_data_import_manager),
) -> OfficialWorkbookSheets:
    """Lista las hojas del archivo Excel para que el usuario seleccione cuál importar."""
    filename = file.filename or "archivo.xlsm"
    lowered = filename.lower()
    if not (lowered.endswith(".xlsm") or lowered.endswith(".xlsx")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser .xlsm o .xlsx.",
        )
    content = file.file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo está vacío.",
        )
    try:
        sheets = OfficialImportService.list_workbook_sheets(filename=filename, content=content)
        return OfficialWorkbookSheets(filename=filename, sheets=sheets)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo leer el Excel: {exc}",
        ) from exc


@router.post("/xlsm")
def import_official_xlsm(
    file: UploadFile = File(...),
    sheet_name: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_official_data_import_manager),
) -> dict:
    """Importa datos oficiales desde Excel (sincrónico, devuelve JSON).

    Los timeslices del SAND se agregan automáticamente a 1 solo
    (promedio para CapacityFactor, suma para los demás).
    """
    filename = file.filename or "archivo.xlsm"
    lowered = filename.lower()
    if not (lowered.endswith(".xlsm") or lowered.endswith(".xlsx")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser .xlsm o .xlsx.",
        )
    content = file.file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo está vacío.",
        )

    result = OfficialImportService.import_xlsm(
        db,
        filename=filename,
        content=content,
        imported_by=current_user.username,
        selected_sheet_name=sheet_name,
        use_default_scenario=True,
        replace_scenario_data=True,
    )

    if result["inserted"] + result["updated"] == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "El archivo se leyó pero no se pudo mapear al formato de carga esperado. "
                "Verifica nombres de hojas y estructura de columnas."
            ),
        )

    return result
