"""Punto de entrada de la aplicación FastAPI.

Responsabilidades:
  - Construir la instancia de FastAPI con título y OpenAPI.
  - Configurar logging y middlewares (CORS según CORS_ORIGINS).
  - Registrar routers versionados bajo API_V1_STR (/api/v1).
  - En startup: verificar disponibilidad de solvers (HiGHS, GLPK).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
import logging

from app.api.v1.api import router as api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.simulation.core.solver import get_solver_availability

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Factory de la aplicación para facilitar testing y despliegue."""
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.project_name,
        openapi_url=f"{settings.api_v1_str}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    cors_origins = settings.cors_origins_list()
    if cors_origins:
        # En producción, restringe `CORS_ORIGINS` a dominios conocidos.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_middleware(GZipMiddleware, minimum_size=1000)

    app.include_router(api_router, prefix=settings.api_v1_str)

    @app.on_event("startup")
    def log_solver_availability() -> None:
        availability = get_solver_availability()
        missing = [name for name, enabled in availability.items() if not enabled]
        if missing:
            logger.warning(
                "Solvers faltantes en entorno: %s. Disponibilidad: %s",
                ", ".join(missing),
                availability,
            )
        else:
            logger.info("Todos los solvers configurados están disponibles: %s", availability)

    return app


app = create_app()


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Ensamblar aplicación FastAPI y registrar componentes transversales.
#
# Posibles mejoras:
# - Añadir startup/shutdown handlers para checks de infraestructura.
#
# Riesgos en producción:
# - Configuración CORS demasiado abierta puede incrementar superficie de ataque.
#
# Escalabilidad:
# - Stateless por diseño; escala horizontal con balanceador.
