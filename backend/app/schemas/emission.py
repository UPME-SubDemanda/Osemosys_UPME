"""Schemas Pydantic para `Emission` (schema `osemosys`)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class EmissionCreate(BaseModel):
    """Payload para crear emisión."""

    name: str = Field(min_length=1, max_length=255)


class EmissionUpdate(BaseModel):
    """Payload para actualizar emisión."""

    name: str = Field(min_length=1, max_length=255)
    justification: str | None = Field(default=None, max_length=2000)


class EmissionPublic(BaseModel):
    """Representación pública de emisión."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Contratos de catálogo de emisiones y su exposición API.
#
# Posibles mejoras:
# - Añadir tipo de emisión y factor CO2e de referencia.
#
# Riesgos en producción:
# - Cambios de forma pueden invalidar serialización existente.
#
# Escalabilidad:
# - Validación simple.

