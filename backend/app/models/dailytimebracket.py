"""Modelo ORM para conjunto `Dailytimebracket`."""

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Dailytimebracket(Base):
    """Franjas horarias intradiarias para el modelo."""

    __tablename__ = "dailytimebracket"
    __table_args__ = (
        UniqueConstraint("code", name="dailytimebracket_code"),
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
# - Segmentar horas del día para restricciones/variables temporales.
#
# Posibles mejoras:
# - Añadir orden y límites horarios explícitos.
#
# Riesgos en producción:
# - Definiciones superpuestas generan resultados inconsistentes.
#
# Escalabilidad:
# - Catálogo de baja cardinalidad.
