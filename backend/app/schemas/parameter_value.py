"""Schemas Pydantic para `parameter_value` (valores por defecto, sin escenario)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ParameterValueCreate(BaseModel):
    """Payload para crear un valor por defecto."""

    id_parameter: int
    id_region: int
    id_solver: int | None = None

    id_technology: int | None = None
    id_fuel: int | None = None
    id_emission: int | None = None

    mode_of_operation: bool = False
    year: int = Field(ge=0, le=3000)
    value: float
    unit: str | None = Field(default=None, max_length=64)


class ParameterValuePublic(BaseModel):
    """DTO de lectura para `parameter_value`."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    id_parameter: int
    id_region: int
    id_solver: int
    id_technology: int | None
    id_fuel: int | None
    id_emission: int | None
    mode_of_operation: bool
    year: int
    value: float
    unit: str | None


class ParameterValueUpdate(BaseModel):
    """Payload de actualización parcial de valor/unidad."""

    value: float
    unit: str | None = Field(default=None, max_length=64)
