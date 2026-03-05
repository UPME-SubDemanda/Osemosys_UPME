"""Utilidades de seguridad: hashing de passwords y JWT.

Notas:
- Passwords: se almacenan como hash usando `pbkdf2_sha256` vía Passlib.
- JWT: HS256 con `SECRET_KEY` en variables de entorno.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

# `pbkdf2_sha256` evita dependencias binarias extra y mantiene compatibilidad
# total con Python puro en entornos Docker/local.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

ALGORITHM = "HS256"


def get_password_hash(password: str) -> str:
    """Genera hash de contraseña con `pbkdf2_sha256`."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica contraseña en texto plano contra hash persistido."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    """Crea JWT firmado con claim `sub`.

    Args:
        subject: Identificador principal (id de usuario en este proyecto).
        expires_minutes: Minutos de expiración opcionales.
    """
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Primitive de seguridad para autenticación basada en password + JWT.
#
# Posibles mejoras:
# - Rotación de claves JWT y soporte de `kid`.
# - Claims adicionales (`iat`, `iss`, `aud`) para políticas más estrictas.
#
# Riesgos en producción:
# - Si `SECRET_KEY` se filtra, se compromete integridad de tokens.
#
# Escalabilidad:
# - Hashing es CPU-bound ligero/moderado; JWT encode es bajo costo.

