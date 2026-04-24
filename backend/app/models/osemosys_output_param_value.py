"""Modelo ORM para resultados de simulacion almacenados en BD."""

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OsemosysOutputParamValue(Base):
    """Fila de resultado de una corrida de simulacion.

    Cubre las 48 variables del modelo abstracto. Las dimensiones relevantes
    viven en columnas tipadas (``id_region``, ``id_technology``, ``id_fuel``,
    ``id_emission``, ``id_timeslice``, ``id_mode_of_operation``,
    ``id_storage``, ``id_season``, ``id_daytype``, ``id_dailytimebracket``,
    ``year``); ``index_json`` queda como respaldo para casos no previstos.
    """

    __tablename__ = "osemosys_output_param_value"
    __table_args__ = (
        Index("ix_oopv_simulation_job", "id_simulation_job"),
        Index("ix_oopv_job_variable", "id_simulation_job", "variable_name"),
        Index(
            "ix_oopv_job_var_region_year",
            "id_simulation_job",
            "variable_name",
            "id_region",
            "year",
        ),
        Index(
            "ix_oopv_job_var_tech",
            "id_simulation_job",
            "variable_name",
            "id_technology",
        ),
        {"schema": "osemosys"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_simulation_job: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("osemosys.simulation_job.id", ondelete="CASCADE"),
        nullable=False,
    )
    variable_name: Mapped[str] = mapped_column(String(128), nullable=False)

    id_region: Mapped[int | None] = mapped_column(Integer, nullable=True)
    id_technology: Mapped[int | None] = mapped_column(Integer, nullable=True)
    id_fuel: Mapped[int | None] = mapped_column(Integer, nullable=True)
    id_emission: Mapped[int | None] = mapped_column(Integer, nullable=True)
    id_timeslice: Mapped[int | None] = mapped_column(Integer, nullable=True)
    id_mode_of_operation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    id_storage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    id_season: Mapped[int | None] = mapped_column(Integer, nullable=True)
    id_daytype: Mapped[int | None] = mapped_column(Integer, nullable=True)
    id_dailytimebracket: Mapped[int | None] = mapped_column(Integer, nullable=True)

    technology_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fuel_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    emission_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    value: Mapped[float] = mapped_column(Float, nullable=False)
    value2: Mapped[float | None] = mapped_column(Float, nullable=True)

    index_json: Mapped[object | None] = mapped_column(JSON, nullable=True)
