"""Modelo ORM para valores por defecto de parámetros (sin escenario)."""

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ParameterValue(Base):
    """Valor por defecto de parámetro del modelo (schema `osemosys`).

    Almacena los datos base importados desde la carga oficial.
    Al crear un escenario nuevo, estos valores se copian a `osemosys_param_value`.
    """

    __tablename__ = "parameter_value"
    __table_args__ = (
        UniqueConstraint(
            "id_parameter", "id_region", "id_technology", "id_fuel",
            "id_emission", "id_solver", "year",
            name="uq_parameter_value_dims",
        ),
        Index("ix_parameter_value_id_parameter", "id_parameter"),
        Index("ix_parameter_value_id_region", "id_region"),
        Index("ix_parameter_value_id_technology", "id_technology"),
        Index("ix_parameter_value_id_fuel", "id_fuel"),
        Index("ix_parameter_value_id_emission", "id_emission"),
        Index("ix_parameter_value_id_solver", "id_solver"),
        {"schema": "osemosys"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    id_parameter: Mapped[int] = mapped_column(
        Integer, ForeignKey("osemosys.parameter.id", ondelete="RESTRICT"), nullable=False
    )
    id_region: Mapped[int] = mapped_column(
        Integer, ForeignKey("osemosys.region.id", ondelete="RESTRICT"), nullable=False
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
    id_solver: Mapped[int] = mapped_column(
        Integer, ForeignKey("osemosys.solver.id", ondelete="RESTRICT"), nullable=False
    )

    mode_of_operation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)

    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
