from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración central de la aplicación.

    Las variables se leen desde entorno (y `.env` en desarrollo) para facilitar
    despliegues Docker/on-prem sin cambios de código. Incluye: API, BD, Redis,
    simulación (concurrencia, límites), autenticación (JWT, secret_key).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field(default="local", alias="ENVIRONMENT")
    project_name: str = Field(default="OSeMOSYS API", alias="PROJECT_NAME")
    api_v1_str: str = Field(default="/api/v1", alias="API_V1_STR")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Coma-separado en .env.
    # Default para desarrollo local con Vite.
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )

    # Database
    database_url: str = Field(
        default="postgresql+psycopg://osemosys:osemosys@localhost:5432/osemosys",
        alias="DATABASE_URL",
    )
    db_schema_osemosys: str = Field(default="osemosys", alias="DB_SCHEMA_OSEMOSYS")

    # Queue / simulation
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    sim_max_concurrency: int = Field(default=3, alias="SIM_MAX_CONCURRENCY")
    sim_user_active_limit: int = Field(default=1, alias="SIM_USER_ACTIVE_LIMIT")

    # Auth
    secret_key: str = Field(default="change-me", alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    def cors_origins_list(self) -> list[str]:
        """Convierte `CORS_ORIGINS` coma-separado a lista normalizada."""
        if not self.cors_origins:
            return []
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Retorna settings cacheados por proceso.

    Evita recalcular/parsear configuración en cada request.
    """
    return Settings()


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Concentrar configuración runtime para API, seguridad y simulación.
#
# Posibles mejoras:
# - Separar settings por dominio (API, DB, worker) con sub-modelos.
#
# Riesgos en producción:
# - Valores inseguros por defecto (e.g., `SECRET_KEY`) requieren override obligatorio.
#
# Escalabilidad:
# - Lectura cacheada O(1), sin impacto en hot path.
