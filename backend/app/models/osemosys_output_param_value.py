"""Modelo ORM para resultados de simulacion almacenados en BD."""

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OsemosysOutputParamValue(Base):
    """Fila de resultado de una corrida de simulacion.

    Almacena las 4 series principales (Dispatch, NewCapacity, UnmetDemand,
    AnnualEmissions) con columnas dimensionales tipadas, y las variables
    intermedias (ProductionByTechnology, TotalCapacityAnnual, storage, etc.)
    usando ``index_json`` para preservar el indice multi-dimensional.
    """

    __tablename__ = "osemosys_output_param_value"
    __table_args__ = (
        Index("ix_oopv_simulation_job", "id_simulation_job"),
        Index("ix_oopv_job_variable", "id_simulation_job", "variable_name"),
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
    technology_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fuel_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    emission_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    value: Mapped[float] = mapped_column(Float, nullable=False)
    value2: Mapped[float | None] = mapped_column(Float, nullable=True)

    index_json: Mapped[object | None] = mapped_column(JSON, nullable=True)
