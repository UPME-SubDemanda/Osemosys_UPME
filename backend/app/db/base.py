"""Base declarativa y convención de nombres.

Este módulo centraliza la `Base` de SQLAlchemy para que:
- Todas las tablas compartan un mismo `MetaData`.
- Las constraints/índices tengan nombres determinísticos (útil para Alembic).
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base declarativa común para todos los modelos ORM."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Definir metadata global y convención de nombres para constraints/índices.
#
# Posibles mejoras:
# - Añadir utilidades para inspección de metadata en health checks.
#
# Riesgos en producción:
# - Cambiar naming convention en caliente complica migraciones históricas.
#
# Escalabilidad:
# - Sin impacto en runtime request-per-request.
