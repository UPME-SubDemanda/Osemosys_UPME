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

# Importa todos los modelos para registrar metadata
import app.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        version_table_schema="public",
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table_schema="public",
            compare_type=True,
        )

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
