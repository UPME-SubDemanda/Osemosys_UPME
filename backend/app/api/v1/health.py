"""Healthcheck endpoints.

Incluye verificación liviana (`/health`) y readiness (`/health/ready`).
"""

from fastapi import APIRouter, HTTPException, status
from redis import Redis
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import SessionLocal

router = APIRouter()


@router.get("/health")
def healthcheck() -> dict[str, str]:
    """Retorna estado básico del servicio.

    Método HTTP:
        - `GET` por tratarse de lectura sin efectos laterales.

    Respuestas:
        - 200: proceso API disponible.
    """
    return {"status": "ok"}


@router.get("/health/ready")
def readiness_check() -> dict[str, str]:
    """Valida disponibilidad de dependencias críticas (DB + Redis)."""
    checks = {"database": "unknown", "redis": "unknown"}

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "degraded",
                "database": "error",
                "redis": checks["redis"],
                "error": str(exc),
            },
        ) from exc

    settings = get_settings()
    redis_client = Redis.from_url(settings.redis_url)
    try:
        redis_client.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "degraded",
                "database": checks["database"],
                "redis": "error",
                "error": str(exc),
            },
        ) from exc
    finally:
        redis_client.close()

    return {"status": "ok", "database": checks["database"], "redis": checks["redis"]}


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Proveer probes de liveness (`/health`) y readiness (`/health/ready`).
#
# Posibles mejoras:
# - Incluir check opcional de worker Celery para readiness extendido.
#
# Riesgos en producción:
# - Un health superficial puede reportar "ok" con dependencias críticas caídas.
#
# Escalabilidad:
# - Coste O(1), apto para alta frecuencia de probes.
