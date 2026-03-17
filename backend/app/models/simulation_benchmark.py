"""Modelo ORM para referencias de paridad numérica."""

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SimulationBenchmark(Base):
    """Valor benchmark para validar resultados backend vs referencia."""

    __tablename__ = "simulation_benchmark"
    __table_args__ = {"schema": "osemosys"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    benchmark_key: Mapped[str] = mapped_column(String(128), nullable=False)
    scenario_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="notebook")
    objective_value: Mapped[float] = mapped_column(nullable=False)
    metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Almacenar baseline numérico para pruebas de regresión del solver.
#
# Posibles mejoras:
# - Añadir tolerancias por métrica y versión de dataset.
#
# Riesgos en producción:
# - Benchmarks obsoletos pueden generar falsos positivos/negativos.
#
# Escalabilidad:
# - Volumen bajo; lecturas en validación.
