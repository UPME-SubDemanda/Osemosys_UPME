"""Schemas Pydantic para escenarios y permisos (schema `osemosys`)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.official_import import OfficialImportResult


EditPolicy = Literal["OWNER_ONLY", "OPEN", "RESTRICTED"]
ScenarioPermissionScope = Literal["mine", "readable", "editable", "readonly"]


class ScenarioCreate(BaseModel):
    """Payload de creación de escenario."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    edit_policy: EditPolicy = "OWNER_ONLY"
    is_template: bool = False


class ScenarioClone(BaseModel):
    """Payload para clonar un escenario existente."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    edit_policy: EditPolicy = "OWNER_ONLY"


class ScenarioUpdate(BaseModel):
    """Payload de actualización de metadatos de escenario."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    edit_policy: EditPolicy | None = None

    @model_validator(mode="after")
    def _validate_any_field(self):
        if self.name is None and self.description is None and self.edit_policy is None:
            raise ValueError("Debes enviar al menos `name`, `description` o `edit_policy`.")
        return self


class ScenarioAccessPublic(BaseModel):
    """Permisos efectivos del usuario autenticado sobre el escenario."""

    can_view: bool
    is_owner: bool
    can_edit_direct: bool
    can_propose: bool
    can_manage_values: bool


class ScenarioPublic(BaseModel):
    """Representación pública de escenario."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    owner: str
    base_scenario_id: int | None = None
    base_scenario_name: str | None = None
    changed_param_names: list[str] = Field(default_factory=list)
    edit_policy: str
    is_template: bool
    created_at: datetime
    effective_access: ScenarioAccessPublic | None = None


class ScenarioPermissionCreate(BaseModel):
    """Crea/actualiza permisos de un usuario sobre un escenario."""

    user_id: uuid.UUID | None = None
    user_identifier: str | None = Field(
        default=None,
        description="Opcional. Si no se envía y viene `user_id`, se usa `user:<uuid>`.",
    )
    can_edit_direct: bool = False
    can_propose: bool = False
    can_manage_values: bool = False

    @model_validator(mode="after")
    def _validate_user_ref(self):
        if self.user_id is None and not (self.user_identifier and self.user_identifier.strip()):
            raise ValueError("Debes enviar `user_identifier` o `user_id`.")
        return self


class ScenarioPermissionPublic(BaseModel):
    """Representación pública de permiso por escenario."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    id_scenario: int
    user_identifier: str
    user_id: uuid.UUID | None
    can_edit_direct: bool
    can_propose: bool
    can_manage_values: bool


class ScenarioExcelImportResponse(BaseModel):
    """Resultado de crear un escenario e importar un Excel a ese escenario."""

    scenario: ScenarioPublic
    import_result: OfficialImportResult


class ScenarioExcelUpdateResponse(BaseModel):
    """Resultado de actualizar un escenario existente desde un Excel SAND."""

    updated: int
    not_found: int
    total_rows_read: int
    warnings: list[str]


class ExcelUpdatePreviewRow(BaseModel):
    """Una fila del preview: registro existente que cambiaría de valor."""

    row_id: int
    param_name: str
    region_name: str | None = None
    technology_name: str | None = None
    fuel_name: str | None = None
    emission_name: str | None = None
    year: int | None = None
    old_value: float
    new_value: float


class ScenarioExcelPreviewResponse(BaseModel):
    """Resultado del preview de actualización desde Excel."""

    changes: list[ExcelUpdatePreviewRow]
    not_found: int
    total_rows_read: int
    warnings: list[str]


class ExcelChangeToApply(BaseModel):
    """Un cambio confirmado por el usuario para aplicar."""

    row_id: int
    new_value: float


class ApplyExcelChangesRequest(BaseModel):
    """Payload para aplicar cambios confirmados tras preview."""

    changes: list[ExcelChangeToApply]


class ScenarioOsemosysYearSummary(BaseModel):
    """Resumen agregado por parámetro y año en `osemosys_param_value`."""

    param_name: str
    year: int | None
    records: int
    total_value: float


class ScenarioOsemosysValueCreate(BaseModel):
    """Crea un valor específico en `osemosys_param_value` para un escenario."""

    param_name: str = Field(min_length=1, max_length=128)
    region_name: str | None = None
    technology_name: str | None = None
    fuel_name: str | None = None
    emission_name: str | None = None
    udc_name: str | None = Field(
        default=None,
        description="Nombre del UDC (code en catálogo `udc_set`) para dimensionar id_udc_set.",
    )
    year: int | None = Field(default=None, ge=0, le=3000)
    value: float


class ScenarioOsemosysValueUpdate(BaseModel):
    """Actualiza dimensiones/valor de una fila en `osemosys_param_value`."""

    param_name: str = Field(min_length=1, max_length=128)
    region_name: str | None = None
    technology_name: str | None = None
    fuel_name: str | None = None
    emission_name: str | None = None
    udc_name: str | None = Field(
        default=None,
        description="Nombre del UDC (code en catálogo `udc_set`) para dimensionar id_udc_set.",
    )
    year: int | None = Field(default=None, ge=0, le=3000)
    value: float


class ScenarioOsemosysValuePublic(BaseModel):
    """Representación pública detallada de `osemosys_param_value`."""

    id: int
    id_scenario: int
    param_name: str
    region_name: str | None = None
    technology_name: str | None = None
    fuel_name: str | None = None
    emission_name: str | None = None
    udc_name: str | None = None
    year: int | None = None
    value: float


class OsemosysValuesPage(BaseModel):
    """Respuesta paginada de valores OSeMOSYS."""

    items: list[ScenarioOsemosysValuePublic]
    total: int
    offset: int
    limit: int


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Definir contratos de escenarios y permisos granulares.
#
# Posibles mejoras:
# - Introducir enums dedicados para políticas/estados de permisos.
#
# Riesgos en producción:
# - Cambios en `EditPolicy` impactan reglas de negocio y frontend.
#
# Escalabilidad:
# - Validación ligera.
