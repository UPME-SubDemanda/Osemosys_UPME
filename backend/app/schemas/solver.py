"""Schemas Pydantic para `Solver` (schema `osemosys`)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SolverCreate(BaseModel):
    """Payload para crear solver."""

    name: str = Field(min_length=1, max_length=255)


class SolverUpdate(BaseModel):
    """Payload para actualizar solver."""

    name: str = Field(min_length=1, max_length=255)
    justification: str | None = Field(default=None, max_length=2000)


class SolverPublic(BaseModel):
    """Representación pública de solver."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Contratos API para catálogo de solvers.
#
# Posibles mejoras:
# - Exponer capacidades/flags soportados por solver.
#
# Riesgos en producción:
# - Cambios pueden afectar selección de solver en frontend.
#
# Escalabilidad:
# - Bajo costo.

