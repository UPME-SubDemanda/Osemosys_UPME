"""Excepciones de dominio para desacoplar services de FastAPI.

Los `services` deben levantar estas excepciones y los endpoints convertirlas a HTTP.
"""


class NotFoundError(Exception):
    """Recurso no encontrado."""


class ConflictError(Exception):
    """Violación de unicidad o conflicto de negocio."""


class ReferencedError(Exception):
    """El recurso está referenciado por otra entidad (no se puede borrar)."""


class ForbiddenError(Exception):
    """El usuario no tiene permisos para realizar la acción."""


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Definir errores de dominio transport-agnostic para servicios/repositorios.
#
# Posibles mejoras:
# - Añadir códigos internos de error para observabilidad y troubleshooting.
#
# Riesgos en producción:
# - Si no se mapean consistentemente en API, puede haber respuestas HTTP ambiguas.
#
# Escalabilidad:
# - No aplica.

