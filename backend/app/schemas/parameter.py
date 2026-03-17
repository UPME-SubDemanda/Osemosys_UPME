"""Schemas Pydantic para `Parameter` (schema `osemosys`)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ParameterCreate(BaseModel):
    """Payload para crear parámetro de catálogo."""

    name: str = Field(min_length=1, max_length=255)


class ParameterUpdate(BaseModel):
    """Payload para actualizar nombre de parámetro."""

    name: str = Field(min_length=1, max_length=255)
    justification: str | None = Field(default=None, max_length=2000)


class ParameterPublic(BaseModel):
    """Representación pública de parámetro."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Contratos de entrada/salida para endpoints de `parameter`.
#
# Posibles mejoras:
# - Añadir campos descriptivos de negocio y metadatos técnicos.
#
# Riesgos en producción:
# - Restricciones de longitud cambian validación y pueden afectar clientes.
#
# Escalabilidad:
# - Validación ligera.

