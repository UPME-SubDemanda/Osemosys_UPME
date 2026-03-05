"""Schemas Pydantic para `Region` (schema `osemosys`)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RegionCreate(BaseModel):
    """Payload para crear región."""

    name: str = Field(min_length=1, max_length=255)


class RegionUpdate(BaseModel):
    """Payload para actualizar región."""

    name: str = Field(min_length=1, max_length=255)
    justification: str | None = Field(default=None, max_length=2000)


class RegionPublic(BaseModel):
    """Representación pública de región."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Definir contratos API para catálogo de regiones.
#
# Posibles mejoras:
# - Incluir código regional normalizado además de nombre.
#
# Riesgos en producción:
# - Cambios de contrato requieren coordinación frontend-backend.
#
# Escalabilidad:
# - Validación de bajo costo.

