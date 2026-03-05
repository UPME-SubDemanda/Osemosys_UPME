"""Utilidades de paginación estandarizada para endpoints de listado.

Convención del proyecto:
- `offset` representa `page` (1-based).
- `cantidad` representa `page_size`.
"""

from __future__ import annotations

from app.schemas.pagination import PaginationMeta


def normalize_pagination(offset: int | None, cantidad: int | None) -> tuple[int, int, int]:
    """Normaliza parámetros de paginación y calcula desplazamiento SQL.

    Args:
        offset: Número de página 1-based.
        cantidad: Tamaño de página solicitado.

    Returns:
        Tupla `(page, page_size, row_offset)` apta para consultas paginadas.

    Notas:
        - Se aplican límites defensivos para evitar consultas excesivas.
    """
    page = offset or 1
    page_size = cantidad or 25

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 1
    if page_size > 200:
        page_size = 200

    row_offset = (page - 1) * page_size
    return page, page_size, row_offset


def build_meta(page: int, page_size: int, total: int, busqueda: str | None) -> PaginationMeta:
    """Construye metadata de paginación homogénea para respuestas API."""
    return PaginationMeta(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=PaginationMeta.compute_total_pages(total, page_size),
        busqueda=busqueda,
    )


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Uniformar paginación para evitar divergencia entre endpoints.
#
# Posibles mejoras:
# - Soportar cursores para datasets muy grandes.
#
# Riesgos en producción:
# - Paginación offset-based puede degradar en páginas altas sobre tablas grandes.
#
# Escalabilidad:
# - Adecuado para volúmenes medios; para gran escala considerar keyset pagination.

