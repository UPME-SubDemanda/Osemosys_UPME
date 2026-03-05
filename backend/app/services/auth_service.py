"""Servicio de autenticación y emisión de token.

Mantiene la lógica de login fuera del endpoint para sostener separación por capas
y facilitar pruebas unitarias de seguridad.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.schemas.token import Token
from app.services.user_service import UserService


class AuthService:
    """Lógica de autenticación basada en usuario/password."""

    @staticmethod
    def login(db: Session, *, username: str, password: str) -> Token | None:
        """Valida credenciales y retorna token de acceso.

        Args:
            db: Sesión SQLAlchemy activa.
            username: Nombre de usuario (no se acepta email).
            password: Contraseña en texto plano.

        Returns:
            Token generado si las credenciales son válidas; `None` si fallan.

        Seguridad:
            - No diferencia explícitamente entre "usuario inexistente" y
              "password inválido" para reducir enumeración de cuentas.

        Rendimiento:
            - I/O-bound por consulta de usuario.
            - CPU-bound ligero por verificación de hash de contraseña.
        """
        user = UserService.get_by_username(db, username=username)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        token = create_access_token(subject=str(user.id))
        return Token(access_token=token)


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Resolver autenticación y emisión de JWT de forma desacoplada del transporte HTTP.
#
# Posibles mejoras:
# - Añadir lockout progresivo por intentos fallidos.
# - Registrar eventos de autenticación para observabilidad y auditoría.
#
# Riesgos en producción:
# - Sin rate limiting, el login puede ser objetivo de ataques de fuerza bruta.
#
# Escalabilidad:
# - Escala horizontalmente con API; costo principal en hash verification.

