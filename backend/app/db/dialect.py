"""Utilidades de compatibilidad entre PostgreSQL y SQLite."""

from __future__ import annotations

from app.core.config import get_settings

SCHEMA_CORE = "core"
SCHEMA_OSEMOSYS = "osemosys"


def is_sqlite_mode() -> bool:
    """Retorna True cuando el backend está configurado para SQLite."""
    return get_settings().is_sqlite()


def schema_translate_map() -> dict[str, str | None]:
    """Mapeo de schemas para SQLAlchemy según dialecto activo."""
    if is_sqlite_mode():
        return {SCHEMA_CORE: None, SCHEMA_OSEMOSYS: None}
    return {}


def osemosys_table(table_name: str) -> str:
    """Retorna referencia SQL calificada para tabla de dominio OSeMOSYS."""
    if is_sqlite_mode():
        return table_name
    return f"{SCHEMA_OSEMOSYS}.{table_name}"

