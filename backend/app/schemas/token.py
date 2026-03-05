"""Schemas de autenticación y transporte de token JWT."""

from pydantic import BaseModel


class Token(BaseModel):
    """Respuesta estándar de autenticación OAuth2 password flow."""

    access_token: str
    token_type: str = "bearer"


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Definir contrato de respuesta de login.
#
# Posibles mejoras:
# - Añadir `expires_in` para mejor UX en frontend.
#
# Riesgos en producción:
# - Cambiar estructura rompe clientes que esperan este shape.
#
# Escalabilidad:
# - No aplica.

