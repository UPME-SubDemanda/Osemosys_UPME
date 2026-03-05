"""Contratos Pydantic de entrada/salida para la API."""

__all__ = []


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Namespace de esquemas serializables y validación de payloads.
#
# Posibles mejoras:
# - Exportar tipos públicos estables para SDK interno.
#
# Riesgos en producción:
# - Cambios incompatibles aquí impactan inmediatamente frontend/integraciones.
#
# Escalabilidad:
# - Validación CPU-bound ligera por request.
