"""Schemas Pydantic para el Data Explorer de resultados (formato wide)."""

from __future__ import annotations

from pydantic import BaseModel


class OutputValueWideCell(BaseModel):
    """Celda pivotada: id de la fila en `osemosys_output_param_value` y su valor."""

    id: int
    value: float


class OutputValueWideRow(BaseModel):
    """Fila pivotada: combinación de dimensiones + mapa año->celda."""

    group_key: str
    variable_name: str
    region_name: str | None = None
    technology_name: str | None = None
    fuel_name: str | None = None
    emission_name: str | None = None
    timeslice_name: str | None = None
    mode_name: str | None = None
    storage_name: str | None = None
    season_name: str | None = None
    daytype_name: str | None = None
    bracket_name: str | None = None
    cells: dict[str, OutputValueWideCell]


class OutputValuesWidePage(BaseModel):
    """Respuesta paginada (sobre grupos) en formato wide."""

    items: list[OutputValueWideRow]
    total: int
    offset: int
    limit: int
    years: list[int]
    has_scalar: bool


class OutputWideFacets(BaseModel):
    """Valores únicos por columna para el popover de filtros."""

    variable_names: list[str]
    region_names: list[str]
    technology_names: list[str]
    fuel_names: list[str]
    emission_names: list[str]
    timeslice_names: list[str]
    mode_names: list[str]
    storage_names: list[str]


class OutputValuesTotals(BaseModel):
    """Suma total por año (y escalar) aplicando los mismos filtros que el wide."""

    years: dict[str, float]
    scalar: float | None = None
    row_count: int
