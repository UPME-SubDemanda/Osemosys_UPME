"""Schemas Pydantic para los endpoints admin del catálogo de visualización."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
#  Colores
# ---------------------------------------------------------------------------

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

ALLOWED_COLOR_GROUPS = ("fuel", "pwr", "sector", "emission", "family")


class ColorItemPublic(BaseModel):
    id: int
    key: str
    group: str
    color_hex: str
    description: str | None = None
    sort_order: int
    updated_at: datetime


class ColorItemCreate(BaseModel):
    key: str = Field(min_length=1, max_length=128)
    group: str = Field(min_length=1, max_length=32)
    color_hex: str = Field(min_length=4, max_length=9)
    description: str | None = None
    sort_order: int = 0

    @field_validator("color_hex")
    @classmethod
    def _validate_hex(cls, v: str) -> str:
        if not _HEX_RE.match(v):
            raise ValueError("color_hex debe ser '#RRGGBB' o '#RRGGBBAA'.")
        return v.lower()

    @field_validator("group")
    @classmethod
    def _validate_group(cls, v: str) -> str:
        if v not in ALLOWED_COLOR_GROUPS:
            raise ValueError(f"group inválido; permitidos: {ALLOWED_COLOR_GROUPS}")
        return v


class ColorItemUpdate(BaseModel):
    color_hex: str | None = Field(default=None, min_length=4, max_length=9)
    description: str | None = None
    sort_order: int | None = None

    @field_validator("color_hex")
    @classmethod
    def _validate_hex(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _HEX_RE.match(v):
            raise ValueError("color_hex debe ser '#RRGGBB' o '#RRGGBBAA'.")
        return v.lower()


class ColorListResponse(BaseModel):
    items: list[ColorItemPublic]
    total: int
    allowed_groups: list[str] = list(ALLOWED_COLOR_GROUPS)


# ---------------------------------------------------------------------------
#  Labels
# ---------------------------------------------------------------------------

class LabelItemPublic(BaseModel):
    id: int
    code: str
    label_es: str
    label_en: str | None = None
    category: str | None = None
    sort_order: int
    updated_at: datetime


class LabelItemCreate(BaseModel):
    code: str = Field(min_length=1, max_length=128)
    label_es: str = Field(min_length=1, max_length=255)
    label_en: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=64)
    sort_order: int = 0


class LabelItemUpdate(BaseModel):
    label_es: str | None = Field(default=None, max_length=255)
    label_en: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=64)
    sort_order: int | None = None


class LabelListResponse(BaseModel):
    items: list[LabelItemPublic]
    total: int
    offset: int
    limit: int
    categories: list[str]


# ---------------------------------------------------------------------------
#  Audit (historial de cambios)
# ---------------------------------------------------------------------------

class AuditEntryPublic(BaseModel):
    id: int
    table_name: str
    row_id: int | None = None
    action: str
    diff_json: dict | list | None = None
    changed_by_username: str | None = None
    changed_at: datetime


class AuditListResponse(BaseModel):
    items: list[AuditEntryPublic]
    total: int
    offset: int
    limit: int
    tables: list[str]


# ---------------------------------------------------------------------------
#  Sector mapping (prefijo tech → sector)
# ---------------------------------------------------------------------------

class SectorMappingPublic(BaseModel):
    id: int
    tech_prefix: str
    sector_name: str
    sort_order: int
    updated_at: datetime


class SectorMappingCreate(BaseModel):
    tech_prefix: str = Field(min_length=1, max_length=64)
    sector_name: str = Field(min_length=1, max_length=128)
    sort_order: int = 0


class SectorMappingUpdate(BaseModel):
    sector_name: str | None = Field(default=None, min_length=1, max_length=128)
    sort_order: int | None = None


class SectorMappingListResponse(BaseModel):
    items: list[SectorMappingPublic]
    total: int


# ---------------------------------------------------------------------------
#  Tech families
# ---------------------------------------------------------------------------

class TechFamilyItemPublic(BaseModel):
    id: int
    family_code: str
    tech_prefix: str
    sort_order: int
    updated_at: datetime


class TechFamilyItemCreate(BaseModel):
    family_code: str = Field(min_length=1, max_length=64)
    tech_prefix: str = Field(min_length=1, max_length=64)
    sort_order: int = 0


class TechFamilyItemUpdate(BaseModel):
    sort_order: int | None = None


class TechFamilyBulkAdd(BaseModel):
    """Agrega N prefijos a una familia de una sola llamada."""
    family_code: str = Field(min_length=1, max_length=64)
    tech_prefixes: list[str] = Field(min_length=1)


class TechFamilyListResponse(BaseModel):
    items: list[TechFamilyItemPublic]
    total: int
    families: list[str]


# ---------------------------------------------------------------------------
#  Chart modules + submodules (3.3.D)
# ---------------------------------------------------------------------------

class ChartSubmodulePublic(BaseModel):
    id: int
    module_id: int
    code: str
    label: str
    icon: str | None = None
    sort_order: int
    is_visible: bool
    updated_at: datetime


class ChartModulePublic(BaseModel):
    id: int
    code: str
    label: str
    icon: str | None = None
    sort_order: int
    is_visible: bool
    updated_at: datetime
    submodules: list[ChartSubmodulePublic] = []
    chart_count: int = 0


class ChartModuleCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=128)
    icon: str | None = Field(default=None, max_length=16)
    sort_order: int = 0
    is_visible: bool = True


class ChartModuleUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=128)
    icon: str | None = Field(default=None, max_length=16)
    sort_order: int | None = None
    is_visible: bool | None = None


class ChartSubmoduleCreate(BaseModel):
    module_id: int
    code: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=128)
    icon: str | None = Field(default=None, max_length=16)
    sort_order: int = 0
    is_visible: bool = True


class ChartSubmoduleUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=128)
    icon: str | None = Field(default=None, max_length=16)
    sort_order: int | None = None
    is_visible: bool | None = None
    module_id: int | None = None  # permite mover a otra madre


class ChartModulesTreeResponse(BaseModel):
    items: list[ChartModulePublic]


# ---------------------------------------------------------------------------
#  Variable units (3.3.E)
# ---------------------------------------------------------------------------

class VariableUnitPublic(BaseModel):
    id: int
    variable_name: str
    unit_base: str
    display_units_json: list[dict] | None = None
    updated_at: datetime


class VariableUnitCreate(BaseModel):
    variable_name: str = Field(min_length=1, max_length=128)
    unit_base: str = Field(min_length=1, max_length=32)
    display_units_json: list[dict] | None = None


class VariableUnitUpdate(BaseModel):
    unit_base: str | None = Field(default=None, max_length=32)
    display_units_json: list[dict] | None = None


class VariableUnitListResponse(BaseModel):
    items: list[VariableUnitPublic]
    total: int


# ---------------------------------------------------------------------------
#  Chart config (3.3.F) + sub-filtros (3.3.H)
# ---------------------------------------------------------------------------

class ChartSubfilterPublic(BaseModel):
    id: int
    chart_id: int
    group_label: str | None = None
    code: str
    display_label: str | None = None
    sort_order: int
    default_selected: bool


class ChartSubfilterCreate(BaseModel):
    chart_id: int
    group_label: str | None = Field(default=None, max_length=64)
    code: str = Field(min_length=1, max_length=64)
    display_label: str | None = Field(default=None, max_length=128)
    sort_order: int = 0
    default_selected: bool = False


class ChartSubfilterUpdate(BaseModel):
    group_label: str | None = None
    display_label: str | None = None
    sort_order: int | None = None
    default_selected: bool | None = None


class ChartConfigPublic(BaseModel):
    id: int
    tipo: str
    module_id: int
    submodule_id: int | None = None
    label_titulo: str
    label_figura: str | None = None
    variable_default: str
    filtro_kind: str
    filtro_params_json: dict | list | None = None
    agrupar_por_default: str
    agrupaciones_permitidas_json: list[str] | None = None
    color_fn_key: str
    flags_json: dict | None = None
    msg_sin_datos: str | None = None
    data_explorer_filters_json: dict | None = None
    is_visible: bool
    sort_order: int
    subfilters: list[ChartSubfilterPublic] = []
    updated_at: datetime


class ChartConfigCreate(BaseModel):
    tipo: str = Field(min_length=1, max_length=64)
    module_id: int
    submodule_id: int | None = None
    label_titulo: str = Field(min_length=1, max_length=255)
    label_figura: str | None = Field(default=None, max_length=64)
    variable_default: str = Field(min_length=1, max_length=128)
    filtro_kind: str = Field(default="prefix", max_length=64)
    filtro_params_json: dict | list | None = None
    agrupar_por_default: str = "TECNOLOGIA"
    agrupaciones_permitidas_json: list[str] | None = None
    color_fn_key: str = "tecnologias"
    flags_json: dict | None = None
    msg_sin_datos: str | None = None
    data_explorer_filters_json: dict | None = None
    is_visible: bool = True
    sort_order: int = 0


class ChartConfigUpdate(BaseModel):
    module_id: int | None = None
    submodule_id: int | None = None
    label_titulo: str | None = Field(default=None, max_length=255)
    label_figura: str | None = Field(default=None, max_length=64)
    variable_default: str | None = Field(default=None, max_length=128)
    filtro_kind: str | None = Field(default=None, max_length=64)
    filtro_params_json: dict | list | None = None
    agrupar_por_default: str | None = None
    agrupaciones_permitidas_json: list[str] | None = None
    color_fn_key: str | None = None
    flags_json: dict | None = None
    msg_sin_datos: str | None = None
    data_explorer_filters_json: dict | None = None
    is_visible: bool | None = None
    sort_order: int | None = None


class ChartConfigListResponse(BaseModel):
    items: list[ChartConfigPublic]
    total: int
