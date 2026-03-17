"""Schemas Pydantic para `Technology` (schema `osemosys`)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TechnologyCreate(BaseModel):
    """Payload para crear tecnología."""

    name: str = Field(min_length=1, max_length=255)


class TechnologyUpdate(BaseModel):
    """Payload para actualizar tecnología."""

    name: str = Field(min_length=1, max_length=255)
    justification: str | None = Field(default=None, max_length=2000)


class TechnologyPublic(BaseModel):
    """Representación pública de tecnología."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Contratos para operaciones de catálogo tecnológico.
#
# Posibles mejoras:
# - Añadir atributos de clasificación tecnológica.
#
# Riesgos en producción:
# - Contratos no versionados dificultan evolución incremental.
#
# Escalabilidad:
# - Bajo costo.

