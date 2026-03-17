"""Configuración de Alembic.

Características:
- Usa `DATABASE_URL` desde configuración de la app.
- Incluye múltiples schemas de Postgres (`include_schemas=True`).
- Importa `app.models` para registrar todos los modelos en `Base.metadata`.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.base import Base
from app.db.dialect import schema_translate_map

# Importa todos los modelos para registrar metadata
import app.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata

IS_SQLITE = settings.is_sqlite()
SCHEMA_MAP = schema_translate_map()


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    configure_kwargs = dict(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        include_schemas=not IS_SQLITE,
        schema_translate_map=SCHEMA_MAP,
    )
    if not IS_SQLITE:
        configure_kwargs["version_table_schema"] = "public"
    context.configure(**configure_kwargs)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        configure_kwargs = dict(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_schemas=not IS_SQLITE,
            schema_translate_map=SCHEMA_MAP,
        )
        if not IS_SQLITE:
            configure_kwargs["version_table_schema"] = "public"
        context.configure(**configure_kwargs)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Configurar ejecución de migraciones Alembic (offline/online) con metadata global.
#
# Posibles mejoras:
# - Hooks de validación previos a migración en entornos productivos.
#
# Riesgos en producción:
# - `DATABASE_URL` mal configurada puede aplicar migraciones en base incorrecta.
#
# Escalabilidad:
# - Operación administrativa puntual; no parte del hot path.
