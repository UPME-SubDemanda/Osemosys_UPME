"""Modelo ORM para parámetros OSEMOSYS de alta dimensionalidad."""

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OsemosysParamValue(Base):
    """Parámetros multidimensionales OSEMOSYS cargados desde BD."""

    __tablename__ = "osemosys_param_value"
    __table_args__ = (
        UniqueConstraint(
            "id_scenario",
            "param_name",
            "id_region",
            "id_technology",
            "id_fuel",
            "id_emission",
            "id_timeslice",
            "id_mode_of_operation",
            "id_season",
            "id_daytype",
            "id_dailytimebracket",
            "id_storage_set",
            "id_udc_set",
            "year",
            name="uq_osemosys_param_value_dims",
        ),
        Index("ix_osemosys_param_value_scenario", "id_scenario"),
        Index("ix_osemosys_param_value_param", "param_name"),
        Index("ix_osemosys_param_value_year", "year"),
        Index("ix_osemosys_param_value_region_tech_year", "id_region", "id_technology", "year"),
        {"schema": "osemosys"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_scenario: Mapped[int] = mapped_column(
        Integer, ForeignKey("osemosys.scenario.id", ondelete="RESTRICT"), nullable=False
    )
    param_name: Mapped[str] = mapped_column(String(128), nullable=False)

    id_region: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("osemosys.region.id", ondelete="RESTRICT"), nullable=True
    )
    id_technology: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("osemosys.technology.id", ondelete="RESTRICT"), nullable=True
    )
    id_fuel: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("osemosys.fuel.id", ondelete="RESTRICT"), nullable=True
    )
    id_emission: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("osemosys.emission.id", ondelete="RESTRICT"), nullable=True
    )
    id_timeslice: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("osemosys.timeslice.id", ondelete="RESTRICT"), nullable=True
    )
    id_mode_of_operation: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("osemosys.mode_of_operation.id", ondelete="RESTRICT"), nullable=True
    )
    id_season: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("osemosys.season.id", ondelete="RESTRICT"), nullable=True
    )
    id_daytype: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("osemosys.daytype.id", ondelete="RESTRICT"), nullable=True
    )
    id_dailytimebracket: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("osemosys.dailytimebracket.id", ondelete="RESTRICT"), nullable=True
    )
    id_storage_set: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("osemosys.storage_set.id", ondelete="RESTRICT"), nullable=True
    )
    id_udc_set: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("osemosys.udc_set.id", ondelete="RESTRICT"), nullable=True
    )

    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    value: Mapped[float] = mapped_column(nullable=False)


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Persistir cubo multidimensional de parámetros para construir el modelo Pyomo.
#
# Posibles mejoras:
# - Particionar por `id_scenario` y/o `year` en despliegues de gran escala.
#
# Riesgos en producción:
# - Muy alta cardinalidad; índices y constraints impactan costo de escritura.
#
# Escalabilidad:
# - I/O-bound intensivo; requiere tuning de PostgreSQL.
