"""Paquete principal de la aplicación backend."""

__all__ = ["__version__"]

__version__ = "0.1.0"


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Exponer metadatos de versión del paquete `app`.
#
# Posibles mejoras:
# - Automatizar versión desde pipeline CI/CD o etiquetas git.
#
# Riesgos en producción:
# - Divergencia de versión si no existe proceso de release controlado.
#
# Escalabilidad:
# - No aplica.
