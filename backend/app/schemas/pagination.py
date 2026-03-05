"""Schemas Pydantic para paginación y respuesta estándar de listados."""

from __future__ import annotations

from math import ceil
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Metadatos de paginación.

    - `page`: número de página (1-based)
    - `page_size`: tamaño de página
    - `total`: total de registros
    - `total_pages`: total de páginas
    - `busqueda`: término de búsqueda aplicado (si existe)
    """

    page: int
    page_size: int
    total: int
    total_pages: int
    busqueda: str | None = None

    @staticmethod
    def compute_total_pages(total: int, page_size: int) -> int:
        if page_size <= 0:
            return 0
        return int(ceil(total / page_size))


class PaginatedResponse(BaseModel, Generic[T]):
    """Respuesta estándar para listados paginados."""

    model_config = ConfigDict(from_attributes=True)

    data: list[T]
    meta: PaginationMeta


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Estandarizar respuesta paginada para todos los listados.
#
# Posibles mejoras:
# - Incorporar cursor pagination para tablas de gran volumen.
#
# Riesgos en producción:
# - Contrato inconsistente entre endpoints si no se usa este schema de forma uniforme.
#
# Escalabilidad:
# - Costo de serialización bajo; botella principal está en consulta SQL.

