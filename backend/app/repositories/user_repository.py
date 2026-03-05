"""Repositorio para entidad `User` (`core`).

Contiene operaciones de lectura orientadas al flujo de autenticación y perfil.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


class UserRepository:
    """Acceso a datos de usuarios."""

    @staticmethod
    def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
        """Obtiene usuario por clave primaria UUID."""
        return db.get(User, user_id)

    @staticmethod
    def get_by_username(db: Session, username: str) -> User | None:
        """Busca usuario por username (login solo por nombre de usuario)."""
        stmt = select(User).where(User.username == username)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_all(db: Session) -> list[User]:
        """Lista usuarios para administración centralizada de permisos."""
        stmt = select(User).order_by(User.created_at.desc(), User.username.asc())
        return list(db.execute(stmt).scalars().all())


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Proveer consultas base de usuario para capas superiores.
#
# Posibles mejoras:
# - Proyección selectiva de columnas en consultas de autenticación.
#
# Riesgos en producción:
# - Sin índices adecuados en `username`/`email` el login puede degradar.
#
# Escalabilidad:
# - I/O-bound; depende de índices y cardinalidad de usuarios.

