"""Schemas Pydantic para plantillas de gráficas guardadas y generación de reportes."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


CompareMode = Literal["off", "facet"]
ViewMode = Literal["column", "line"]
BarOrientation = Literal["vertical", "horizontal"]
FacetPlacement = Literal["inline", "stacked"]
FacetLegendMode = Literal["shared", "perFacet"]
FilenameMode = Literal["result", "tags"]
ReportFormat = Literal["png", "svg"]


class SavedChartTemplateBase(BaseModel):
    """Campos compartidos entre create/update/public."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    tipo: str = Field(min_length=1, max_length=64)
    un: str = Field(min_length=1, max_length=16)
    sub_filtro: str | None = Field(default=None, max_length=64)
    loc: str | None = Field(default=None, max_length=32)
    variable: str | None = Field(default=None, max_length=64)
    agrupar_por: str | None = Field(default=None, max_length=32)
    view_mode: ViewMode | None = None
    compare_mode: CompareMode = "off"
    bar_orientation: BarOrientation | None = None
    facet_placement: FacetPlacement | None = None
    facet_legend_mode: FacetLegendMode | None = None
    num_scenarios: int = Field(default=1, ge=1, le=10)
    legend_title: str | None = Field(default=None, max_length=255)
    filename_mode: FilenameMode | None = None


class SavedChartTemplateCreate(SavedChartTemplateBase):
    @model_validator(mode="after")
    def _check_scenarios_vs_mode(self):
        if self.compare_mode == "off" and self.num_scenarios != 1:
            raise ValueError("Con compare_mode='off' debe haber exactamente 1 escenario.")
        if self.compare_mode == "facet" and self.num_scenarios < 2:
            raise ValueError("Con compare_mode='facet' se requieren al menos 2 escenarios.")
        return self


class SavedChartTemplateUpdate(BaseModel):
    """Actualización parcial: nombre, descripción y/o visibilidad."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    is_public: bool | None = None

    @model_validator(mode="after")
    def _any_field(self):
        if self.name is None and self.description is None and self.is_public is None:
            raise ValueError("Debes enviar al menos name, description o is_public.")
        return self


class SavedChartTemplatePublic(SavedChartTemplateBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    is_public: bool = False
    owner_username: str | None = None
    is_owner: bool = True


# ---------------------------------------------------------------------------
# Generación de reportes
# ---------------------------------------------------------------------------


class ReportTemplateItem(BaseModel):
    """Un ítem del reporte: plantilla + job_ids asignados."""

    template_id: int
    job_ids: list[int] = Field(min_length=1, max_length=10)


class ReportCategoryExportSub(BaseModel):
    """Sub-categoría con sus ítems (para export estructurado)."""

    id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    items: list[ReportTemplateItem] = Field(default_factory=list)


class ReportCategoryExport(BaseModel):
    """Categoría (nivel superior) con sus ítems y subcategorías opcionales."""

    id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    items: list[ReportTemplateItem] = Field(default_factory=list)
    subcategories: list[ReportCategoryExportSub] = Field(default_factory=list)


class ReportRequest(BaseModel):
    """Lista de plantillas con sus escenarios y formato de salida.

    Dos modos de export:
      - Plano (``organize_by_category=False``): se envía ``items`` y se produce
        un ZIP con ``01_nombre.ext``, ``02_nombre.ext``, etc.
      - Estructurado (``organize_by_category=True``): se envía ``categories``
        con su árbol y el ZIP queda como
        ``01_Categoria/[01_Sub/]01_nombre.ext``.
    """

    items: list[ReportTemplateItem] = Field(default_factory=list, max_length=200)
    fmt: ReportFormat = "png"
    report_name: str | None = Field(default=None, max_length=120)
    organize_by_category: bool = False
    categories: list[ReportCategoryExport] | None = None


# ---------------------------------------------------------------------------
# Layout persistido del reporte (override manual)
# ---------------------------------------------------------------------------


class ReportLayoutSubcategory(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    items: list[int] = Field(default_factory=list)


class ReportLayoutCategory(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    items: list[int] = Field(default_factory=list)
    subcategories: list[ReportLayoutSubcategory] = Field(default_factory=list)


SubcategoryDisplay = Literal["tabs", "accordions"]


class ReportLayout(BaseModel):
    categories: list[ReportLayoutCategory] = Field(default_factory=list)
    #: Cómo se muestran las subcategorías en el dashboard:
    #:   - ``"tabs"`` (default): pestañas seleccionables (una visible).
    #:   - ``"accordions"``: secciones desplegables apiladas verticalmente
    #:     (todas abiertas por defecto).
    subcategory_display: SubcategoryDisplay = "tabs"


# ---------------------------------------------------------------------------
# Reportes guardados (colecciones de plantillas con nombre y descripción)
# ---------------------------------------------------------------------------


class ReportSavedBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    fmt: ReportFormat = "png"
    items: list[int] = Field(
        description="Lista ordenada de IDs de saved_chart_template.",
        min_length=1,
        max_length=100,
    )
    #: Override manual de categorías. ``None`` = usar auto-layout (frontend).
    layout: ReportLayout | None = None


class ReportSavedCreate(ReportSavedBase):
    pass


class ReportSavedUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    fmt: ReportFormat | None = None
    items: list[int] | None = Field(default=None, min_length=1, max_length=100)
    is_public: bool | None = None
    #: Solo aplica si el usuario tiene permiso (``can_manage_catalogs``).
    is_official: bool | None = None
    #: Enviar ``None`` mantiene el layout actual; enviar objeto lo reemplaza;
    #: se permite ``{"categories": []}`` explícitamente para resetear a auto.
    #: Si quieres restaurar auto, envía ``{"layout": null}`` en JSON con ``exclude_none=False``
    #: (nuestro endpoint detecta la ausencia vs. ``null`` vía ``model_fields_set``).
    layout: ReportLayout | None = None


class ReportSavedPublic(ReportSavedBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    is_public: bool = False
    is_official: bool = False
    owner_username: str | None = None
    is_owner: bool = True
