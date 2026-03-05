"""Modelo ORM para conjunto `Daytype`."""

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Daytype(Base):
    """Clasificación de tipos de día (laboral, fin de semana, etc.)."""

    __tablename__ = "daytype"
    __table_args__ = (
        UniqueConstraint("code", name="daytype_code"),
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
# - Representar granularidad de día para perfil temporal.
#
# Posibles mejoras:
# - Integrar jerarquía de calendarios/reglas festivas.
#
# Riesgos en producción:
# - Mapeo incorrecto de daytype impacta balance horario.
#
# Escalabilidad:
# - Muy bajo costo.
