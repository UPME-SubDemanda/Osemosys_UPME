"""Modelo ORM para conjunto `StorageSet`."""

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StorageSet(Base):
    """Catálogo de componentes de almacenamiento del modelo."""

    __tablename__ = "storage_set"
    __table_args__ = (
        UniqueConstraint("code", name="storage_set_code"),
        {"schema": "osemosys"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Identificar activos/unidades de almacenamiento.
#
# Posibles mejoras:
# - Añadir atributos de tecnología y horizonte de vida útil.
#
# Riesgos en producción:
# - Códigos no sincronizados con parámetros de storage.
#
# Escalabilidad:
# - Bajo costo.
