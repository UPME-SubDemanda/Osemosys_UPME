"""Modelo ORM para catálogo `Solver`."""

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Solver(Base):
    """Catálogo de motores de optimización disponibles."""

    __tablename__ = "solver"
    __table_args__ = (
        UniqueConstraint("name", name="solver_name"),
        {"schema": "osemosys"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Registrar solvers habilitados en ejecución de escenarios.
#
# Posibles mejoras:
# - Definir campos de versión y opciones por solver.
#
# Riesgos en producción:
# - Inconsistencias entre nombre catálogo y backend real del solver.
#
# Escalabilidad:
# - Muy bajo costo.
