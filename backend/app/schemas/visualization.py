"""Schemas Pydantic para visualización de resultados OSeMOSYS.

Define los contratos de request/response para los endpoints de gráficas:
single-scenario, multi-scenario (comparación), catálogo de charts y
resumen de resultados.
"""

from __future__ import annotations

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Schemas para gráficas single-scenario
# ---------------------------------------------------------------------------

class ChartSeries(BaseModel):
    """Una serie individual dentro de una gráfica (e.g. una tecnología)."""

    name: str
    data: list[float]
    color: str
    stack: str | None = None


class ChartDataResponse(BaseModel):
    """Respuesta completa para un chart de un solo escenario."""

    categories: list[str]
    series: list[ChartSeries]
    title: str
    yAxisLabel: str


# ---------------------------------------------------------------------------
# Schemas para gráficas de comparación multi-escenario
# ---------------------------------------------------------------------------

class SubplotData(BaseModel):
    """Un subplot correspondiente a un año específico en comparación."""

    year: int
    categories: list[str]
    series: list[ChartSeries]


class CompareChartResponse(BaseModel):
    """Respuesta completa para un chart de comparación multi-escenario."""

    title: str
    subplots: list[SubplotData]
    yAxisLabel: str


class FacetData(BaseModel):
    """Datos de un facet (escenario completo) en comparación facet."""

    scenario_name: str
    job_id: int
    categories: list[str]
    series: list[ChartSeries]


class CompareChartFacetResponse(BaseModel):
    """Respuesta para comparación por escenarios completos (facets)."""

    title: str
    facets: list[FacetData]
    yAxisLabel: str


# ---------------------------------------------------------------------------
# Catálogo de gráficas disponibles
# ---------------------------------------------------------------------------

class ChartCatalogItem(BaseModel):
    """Metadatos de un tipo de gráfica disponible en el sistema."""

    id: str
    label: str
    variable_default: str
    has_sub_filtro: bool = False
    has_loc: bool = False
    sub_filtros: list[str] | None = None
    es_capacidad: bool = False


# ---------------------------------------------------------------------------
# Resumen de resultados de simulación (KPIs)
# ---------------------------------------------------------------------------

class ResultSummaryResponse(BaseModel):
    """Resumen ligero de una corrida exitosa para el header de visualización."""

    job_id: int
    scenario_id: int
    scenario_name: str | None = None
    solver_name: str
    solver_status: str
    objective_value: float
    coverage_ratio: float
    total_demand: float
    total_dispatch: float
    total_unmet: float
    total_co2: float = 0.0
