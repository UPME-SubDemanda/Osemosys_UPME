"""Modelo ORM para catálogo de tipos de documento."""

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocumentType(Base):
    """Catálogo de tipos de documento (schema `core`).

    Ejemplos: Cédula de ciudadanía, Pasaporte, Cédula de extranjería.
    """

    __tablename__ = "document_type"
    __table_args__ = (
        UniqueConstraint("code", name="document_type_code"),
        UniqueConstraint("name", name="document_type_name"),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Normalizar tipologías documentales del usuario.
#
# Posibles mejoras:
# - Añadir campo `is_active` para retiro de tipos sin borrado.
#
# Riesgos en producción:
# - Cambios de `code` pueden afectar integraciones externas si se usan como clave.
#
# Escalabilidad:
# - Tabla de baja cardinalidad.

