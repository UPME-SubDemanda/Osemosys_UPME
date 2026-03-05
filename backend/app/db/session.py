"""Sesión y engine de base de datos (SQLAlchemy síncrono).

Se proveen:
- `engine`: creado desde `DATABASE_URL`.
- `SessionLocal`: fábrica de sesiones.
- `get_db`: dependencia de FastAPI para inyectar `Session` por request.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# `pool_pre_ping` ayuda a evitar conexiones muertas en despliegues largos.
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """Yield de una sesión DB y asegura su cierre al finalizar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Configurar `engine`, fábrica de sesiones y dependencia `get_db` para FastAPI.
#
# Posibles mejoras:
# - Ajustar tamaño de pool por entorno y telemetría de conexiones.
#
# Riesgos en producción:
# - Pool mal dimensionado puede generar latencia o agotamiento de conexiones.
#
# Escalabilidad:
# - I/O-bound; tuning de pool es clave en concurrencia alta.
