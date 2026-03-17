"""Configuración de logging.

Mantiene un formato consistente tanto en local como en contenedores.
"""

import logging


def configure_logging(level: str = "INFO") -> None:
    """Configura logging base de aplicación/procesos worker."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Estandarizar formato y nivel de logging.
#
# Posibles mejoras:
# - Salida JSON estructurada para agregadores (ELK/OpenSearch/Loki).
#
# Riesgos en producción:
# - Logging demasiado verboso puede afectar I/O en carga alta.
#
# Escalabilidad:
# - Bajo costo, pero depende del backend de logs.
