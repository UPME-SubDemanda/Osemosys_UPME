"""Módulo de infraestructura de persistencia (DB)."""

__all__ = ["base", "session"]


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Exponer namespace de componentes de acceso a base de datos.
#
# Posibles mejoras:
# - Exportar helpers transaccionales comunes.
#
# Riesgos en producción:
# - Ninguno directo.
#
# Escalabilidad:
# - No aplica.
