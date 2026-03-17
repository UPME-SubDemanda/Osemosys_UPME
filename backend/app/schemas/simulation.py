"""Schemas de API para ejecución y monitoreo de simulaciones."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SimulationStatus = Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"]
SimulationSolver = Literal["highs", "glpk"]


class SimulationSubmit(BaseModel):
    """Payload para encolar una simulación."""

    scenario_id: int = Field(gt=0)
    solver_name: SimulationSolver = "highs"


class SimulationJobPublic(BaseModel):
    """Estado público de un job de simulación."""

    id: int
    scenario_id: int
    scenario_name: str | None = None
    user_id: str
    username: str | None = None
    solver_name: SimulationSolver
    status: SimulationStatus
    progress: float
    cancel_requested: bool
    queue_position: int | None = None
    result_ref: str | None = None
    error_message: str | None = None
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class SimulationOverviewPublic(BaseModel):
    """Resumen operacional del tablero global de simulaciones."""

    queued_count: int
    running_count: int
    active_count: int
    total_count: int
    services_memory_total_bytes: int = 0


class SimulationLogPublic(BaseModel):
    """Evento/log de progreso de una simulación."""

    id: int
    event_type: str
    stage: str | None
    message: str | None
    progress: float | None
    created_at: datetime


class SimulationResultPublic(BaseModel):
    """Contrato del artefacto final de resultados de simulación."""

    job_id: int
    scenario_id: int
    records_used: int
    osemosys_param_records: int
    objective_value: float
    solver_status: str
    solver_name: SimulationSolver
    coverage_ratio: float
    total_demand: float
    total_dispatch: float
    total_unmet: float
    dispatch: list[dict]
    unmet_demand: list[dict]
    new_capacity: list[dict]
    annual_emissions: list[dict]
    osemosys_inputs_summary: list[dict]
    stage_times: dict = Field(default_factory=dict)
    model_timings: dict = Field(default_factory=dict)
    # Diccionario de solución tipo HiGHS: por variable, lista de {index: [...], value: number}
    sol: dict[str, list[dict]] = Field(default_factory=dict)
    # Variables intermedias tipo GLPK: ProductionByTechnology, UseByTechnology, etc.
    intermediate_variables: dict[str, list[dict]] = Field(default_factory=dict)


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Contratos para envío, monitoreo y consulta de resultados de corridas.
#
# Posibles mejoras:
# - Tipar estructuras `dispatch/unmet/new_capacity` con modelos dedicados.
#
# Riesgos en producción:
# - `list[dict]` flexible acelera cambios pero reduce seguridad de contrato.
#
# Escalabilidad:
# - Serialización potencialmente pesada en resultados de gran tamaño.
