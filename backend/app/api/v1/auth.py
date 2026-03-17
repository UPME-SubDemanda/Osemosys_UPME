"""Endpoints de autenticación y emisión de JWT."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.token import Token
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth")


@router.post("/login", response_model=Token)
def login(
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Token:
    """Autentica un usuario y retorna un token JWT.

    `form_data.username` es el nombre de usuario (no se acepta email).

    Método HTTP:
        - `POST` porque procesa credenciales y genera un recurso temporal
          (token de acceso) no idempotente.

    Respuestas:
        - 200: credenciales válidas, token emitido.
        - 401: credenciales inválidas.

    Seguridad:
        - No expone qué campo falló (usuario/password) para reducir enumeración.
    """
    token = AuthService.login(db, username=form_data.username, password=form_data.password)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña inválidos",
        )
    return token


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Exponer autenticación de entrada al sistema y emisión de JWT.
#
# Posibles mejoras:
# - Rate limiting por IP/usuario para mitigar brute force.
# - Integración de MFA para perfiles críticos.
#
# Riesgos en producción:
# - Endpoint de login es objetivo primario de abuso; requiere monitoreo activo.
#
# Escalabilidad:
# - Carga típicamente I/O-bound (lookup usuario/hash password) y escalable horizontalmente.

