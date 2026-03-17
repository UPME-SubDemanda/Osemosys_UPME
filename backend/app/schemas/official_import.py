from __future__ import annotations

from pydantic import BaseModel


class OfficialImportResult(BaseModel):
    filename: str
    imported_at: str
    imported_by: str
    total_rows_read: int
    inserted: int
    updated: int
    skipped: int
    warnings: list[str]
    """Si el preprocesamiento tipo notebook se aplicó bien, trae los contadores (deleted, completed_*, emission_updated)."""
    notebook_preprocess: dict[str, int] | None = None
    """Si el preprocesamiento falló, aquí viene el mensaje de error; la importación sigue correcta."""
    notebook_preprocess_error: str | None = None


class OfficialWorkbookSheets(BaseModel):
    filename: str
    sheets: list[str]
