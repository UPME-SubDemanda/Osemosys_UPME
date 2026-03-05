"""Repositorio para workflow de solicitudes de cambio."""

from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import ChangeRequest, ChangeRequestValue, OsemosysParamValue


class ChangeRequestRepository:
    """Acceso a datos para `ChangeRequest` y su detalle de valores."""

    @staticmethod
    def get_osemosys_param_value_by_id(
        db: Session, osemosys_param_value_id: int
    ) -> OsemosysParamValue | None:
        """Obtiene `OsemosysParamValue` objetivo de la solicitud."""
        return db.get(OsemosysParamValue, osemosys_param_value_id)

    @staticmethod
    def create_change_request(
        db: Session,
        *,
        id_osemosys_param_value: int,
        created_by: str,
        status: str,
    ) -> ChangeRequest:
        """Inserta cabecera de solicitud de cambio."""
        obj = ChangeRequest(
            id_osemosys_param_value=id_osemosys_param_value,
            created_by=created_by,
            status=status,
        )
        db.add(obj)
        return obj

    @staticmethod
    def create_change_request_value(
        db: Session,
        *,
        id_change_request: int,
        old_value: float,
        new_value: float,
    ) -> ChangeRequestValue:
        """Inserta detalle con valor anterior y valor propuesto."""
        obj = ChangeRequestValue(
            id_change_request=id_change_request,
            old_value=old_value,
            new_value=new_value,
        )
        db.add(obj)
        return obj

    @staticmethod
    def get_by_id(db: Session, change_request_id: int) -> ChangeRequest | None:
        """Obtiene solicitud por id."""
        return db.get(ChangeRequest, change_request_id)

    @staticmethod
    def get_value_by_change_request_id(
        db: Session, *, change_request_id: int
    ) -> ChangeRequestValue | None:
        """Obtiene detalle de una solicitud por su id."""
        stmt = select(ChangeRequestValue).where(
            ChangeRequestValue.id_change_request == change_request_id
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_by_created_by(db: Session, *, created_by: str) -> list[ChangeRequest]:
        """Lista solicitudes creadas por usuario."""
        stmt = (
            select(ChangeRequest)
            .where(ChangeRequest.created_by == created_by)
            .order_by(desc(ChangeRequest.created_at))
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def list_pending_by_scenario(db: Session, *, scenario_id: int) -> list[ChangeRequest]:
        """Lista solicitudes pendientes asociadas a un escenario."""
        stmt = (
            select(ChangeRequest)
            .join(
                OsemosysParamValue,
                OsemosysParamValue.id == ChangeRequest.id_osemosys_param_value,
            )
            .where(
                OsemosysParamValue.id_scenario == scenario_id,
                ChangeRequest.status == "PENDING",
            )
            .order_by(desc(ChangeRequest.created_at))
        )
        return list(db.execute(stmt).scalars().all())


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Persistencia del ciclo de revisión de cambios.
#
# Posibles mejoras:
# - Añadir consultas agregadas para métricas de backlog por escenario.
#
# Riesgos en producción:
# - Dependencia de join con `ParameterValue` requiere índices correctos.
#
# Escalabilidad:
# - I/O-bound; la tabla de historial puede crecer rápido.
