"""Schemas Pydantic para `Fuel` (schema `osemosys`)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FuelCreate(BaseModel):
    """Payload para crear combustible."""

    name: str = Field(min_length=1, max_length=255)


class FuelUpdate(BaseModel):
    """Payload para actualizar combustible."""

    name: str = Field(min_length=1, max_length=255)
    justification: str | None = Field(default=None, max_length=2000)


class FuelPublic(BaseModel):
    """Representación pública de combustible."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Definir contratos del catálogo de combustibles.
#
# Posibles mejoras:
# - Añadir codificación técnica (PCI, unidad base, familia).
#
# Riesgos en producción:
# - Incompatibilidades contractuales impactan formularios frontend.
#
# Escalabilidad:
# - No problemática.

