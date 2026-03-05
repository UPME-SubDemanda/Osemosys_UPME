"""Capa de negocio (`services`) del backend.

Expone contratos de orquestación entre API, repositorios y reglas de dominio.
"""

__all__ = []


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Delimitar espacio de nombres de la capa de servicios.
#
# Posibles mejoras:
# - Exportar explícitamente servicios estables para facilitar imports consistentes.
#
# Riesgos en producción:
# - Ninguno directo (módulo de inicialización).
#
# Escalabilidad:
# - No aplica; sin carga computacional.
