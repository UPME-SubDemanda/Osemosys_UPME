"""Schemas Pydantic para solicitudes de cambio (`change_request`)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ChangeRequestStatus = Literal["PENDING", "APPROVED", "REJECTED"]


class ChangeRequestCreate(BaseModel):
    """Payload para solicitar cambio de un valor existente."""

    id_osemosys_param_value: int
    new_value: float


class ChangeRequestPublic(BaseModel):
    """Respuesta unificada de solicitud de cambio."""

    id: int
    id_osemosys_param_value: int
    created_by: str
    status: ChangeRequestStatus
    old_value: float
    new_value: float
    created_at: datetime
    applied: bool = Field(
        description="`true` cuando el valor ya fue aplicado al `osemosys_param_value`."
    )


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Contratos del workflow de propuestas/aprobaciones de cambios.
#
# Posibles mejoras:
# - Añadir motivo/comentario para auditoría de decisiones.
#
# Riesgos en producción:
# - Evolución de estados requiere sincronización estricta con services/frontend.
#
# Escalabilidad:
# - No significativa.
