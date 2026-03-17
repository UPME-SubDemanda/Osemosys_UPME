"""Modelo ORM para usuario autenticable del esquema `core`."""

import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    """Usuario de autenticación (schema `core`).

    Nota: `hashed_password` almacena el hash del password, nunca el texto plano.
    """

    __tablename__ = "user"
    __table_args__ = (
        UniqueConstraint("email", name="user_email"),
        UniqueConstraint("username", name="user_username"),
        UniqueConstraint("document_number", name="user_document_number"),
        {"schema": "core"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    username: Mapped[str] = mapped_column(String(150), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    document_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    document_type_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("core.document_type.id", ondelete="RESTRICT"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    can_manage_catalogs: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_import_official_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_manage_users: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Persistir identidad de usuario y permisos globales de administración.
#
# Posibles mejoras:
# - Añadir estado de bloqueo y política de expiración de credenciales.
#
# Riesgos en producción:
# - `document_number` único requiere limpieza de datos históricos/migraciones.
#
# Escalabilidad:
# - I/O-bound; índices únicos críticos para login y consistencia.

