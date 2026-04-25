"""Compat layer para lectura de catálogos de visualización.

Este módulo expone la interfaz esperada por ``chart_service`` mientras se
consolida el lector editable basado en BD. Por ahora retorna los diccionarios
hardcodeados existentes para evitar fallos de import y mantener estabilidad.
"""

from __future__ import annotations

from app.visualization.colors import COLORES_EMISIONES, COLORES_GRUPOS
from app.visualization.configs_comparacion import COLORES_SECTOR, MAPA_SECTOR


def get_colores_grupos() -> dict[str, str]:
    """Retorna la paleta de grupos de combustible."""
    return COLORES_GRUPOS


def get_colores_sector() -> dict[str, str]:
    """Retorna la paleta de sectores."""
    return COLORES_SECTOR


def get_colores_emisiones() -> dict[str, str]:
    """Retorna la paleta de emisiones."""
    return COLORES_EMISIONES


def get_mapa_sector() -> dict[str, str]:
    """Retorna el mapeo prefijo de tecnología -> sector."""
    return MAPA_SECTOR
