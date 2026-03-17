"""Servicio de workflow para solicitudes de cambio sobre `OsemosysParamValue`.

Implementa políticas de edición por escenario:
- OWNER_ONLY
- OPEN
- RESTRICTED (según `can_edit_direct` / `can_propose`)
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models import User
from app.repositories.change_request_repository import ChangeRequestRepository
from app.repositories.scenario_repository import ScenarioRepository
from app.services.scenario_service import ScenarioService


class ChangeRequestService:
    """Motor de reglas para creación, aprobación y rechazo de cambios."""

    @staticmethod
    def _can_manage_scenario(db: Session, *, scenario_id: int, current_user: User) -> bool:
        """Valida capacidad de aprobación/rechazo en escenario."""
        scenario = ScenarioRepository.get_by_id(db, scenario_id)
        if not scenario:
            raise NotFoundError("Escenario no encontrado.")
        if scenario.owner == current_user.username:
            return True
        permission = ScenarioRepository.get_permission_for_user(
            db, scenario_id=scenario_id, user_id=current_user.id
        )
        return bool(permission and permission.can_edit_direct)

    @staticmethod
    def _resolve_policy(
        db: Session,
        *,
        scenario_id: int,
        current_user: User,
    ) -> tuple[str, bool]:
        """Resuelve política de edición y modo de aplicación.

        Returns:
            Tupla `(status_inicial, apply_direct)` donde:
            - `status_inicial` es `APPROVED` o `PENDING`.
            - `apply_direct` define si el valor se aplica inmediatamente.
        """
        scenario = ScenarioRepository.get_by_id(db, scenario_id)
        if not scenario:
            raise NotFoundError("Escenario no encontrado.")

        if scenario.owner == current_user.username:
            return "APPROVED", True

        if scenario.edit_policy == "OPEN":
            return "APPROVED", True

        permission = ScenarioRepository.get_permission_for_user(
            db, scenario_id=scenario_id, user_id=current_user.id
        )

        if scenario.edit_policy == "OWNER_ONLY":
            raise ForbiddenError("Solo el owner puede modificar este escenario.")

        if not permission:
            raise ForbiddenError("No tienes permisos sobre este escenario.")

        if permission.can_edit_direct:
            return "APPROVED", True
        if permission.can_propose:
            return "PENDING", False

        raise ForbiddenError("No tienes permisos para proponer o aplicar cambios.")

    @staticmethod
    def _to_public(change_request, change_value):
        """Transforma entidades ORM en payload serializable de respuesta."""
        return {
            "id": change_request.id,
            "id_osemosys_param_value": change_request.id_osemosys_param_value,
            "created_by": change_request.created_by,
            "status": change_request.status,
            "old_value": change_value.old_value,
            "new_value": change_value.new_value,
            "created_at": change_request.created_at,
            "applied": change_request.status == "APPROVED",
        }

    @staticmethod
    def create(
        db: Session,
        *,
        current_user: User,
        id_osemosys_param_value: int,
        new_value: float,
    ) -> dict:
        """Crea solicitud de cambio con aplicación directa o diferida.

        Complejidad:
            - O(1) en lógica, dominada por I/O de base de datos.
        """
        osemosys_value = ChangeRequestRepository.get_osemosys_param_value_by_id(
            db, id_osemosys_param_value
        )
        if not osemosys_value:
            raise NotFoundError("OsemosysParamValue no encontrado.")

        status, apply_direct = ChangeRequestService._resolve_policy(
            db, scenario_id=osemosys_value.id_scenario, current_user=current_user
        )

        change_request = ChangeRequestRepository.create_change_request(
            db,
            id_osemosys_param_value=id_osemosys_param_value,
            created_by=current_user.username,
            status=status,
        )
        db.flush()

        change_value = ChangeRequestRepository.create_change_request_value(
            db,
            id_change_request=change_request.id,
            old_value=osemosys_value.value,
            new_value=new_value,
        )

        if apply_direct:
            osemosys_value.value = new_value
            scenario = ScenarioRepository.get_by_id(db, osemosys_value.id_scenario)
            if scenario is not None:
                ScenarioService._track_changed_params(
                    scenario,
                    param_names=[osemosys_value.param_name],
                )

        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("No se pudo crear la solicitud de cambio.") from e

        db.refresh(change_request)
        db.refresh(change_value)
        return ChangeRequestService._to_public(change_request, change_value)

    @staticmethod
    def approve(db: Session, *, current_user: User, change_request_id: int) -> dict:
        """Aprueba solicitud pendiente y aplica nuevo valor al parámetro."""
        change_request = ChangeRequestRepository.get_by_id(db, change_request_id)
        if not change_request:
            raise NotFoundError("Solicitud de cambio no encontrada.")

        if change_request.status != "PENDING":
            raise ConflictError("Solo se pueden aprobar solicitudes en estado PENDING.")

        osemosys_value = ChangeRequestRepository.get_osemosys_param_value_by_id(
            db, change_request.id_osemosys_param_value
        )
        if not osemosys_value:
            raise NotFoundError("OsemosysParamValue asociado no encontrado.")

        if not ChangeRequestService._can_manage_scenario(
            db, scenario_id=osemosys_value.id_scenario, current_user=current_user
        ):
            raise ForbiddenError("No tienes permisos para aprobar en este escenario.")

        change_value = ChangeRequestRepository.get_value_by_change_request_id(
            db, change_request_id=change_request.id
        )
        if not change_value:
            raise NotFoundError("Detalle de solicitud de cambio no encontrado.")

        change_request.status = "APPROVED"
        osemosys_value.value = change_value.new_value
        scenario = ScenarioRepository.get_by_id(db, osemosys_value.id_scenario)
        if scenario is not None:
            ScenarioService._track_changed_params(
                scenario,
                param_names=[osemosys_value.param_name],
            )
        db.commit()
        db.refresh(change_request)
        return ChangeRequestService._to_public(change_request, change_value)

    @staticmethod
    def reject(db: Session, *, current_user: User, change_request_id: int) -> dict:
        """Rechaza solicitud pendiente sin mutar el valor objetivo."""
        change_request = ChangeRequestRepository.get_by_id(db, change_request_id)
        if not change_request:
            raise NotFoundError("Solicitud de cambio no encontrada.")

        if change_request.status != "PENDING":
            raise ConflictError("Solo se pueden rechazar solicitudes en estado PENDING.")

        osemosys_value = ChangeRequestRepository.get_osemosys_param_value_by_id(
            db, change_request.id_osemosys_param_value
        )
        if not osemosys_value:
            raise NotFoundError("OsemosysParamValue asociado no encontrado.")

        if not ChangeRequestService._can_manage_scenario(
            db, scenario_id=osemosys_value.id_scenario, current_user=current_user
        ):
            raise ForbiddenError("No tienes permisos para rechazar en este escenario.")

        change_value = ChangeRequestRepository.get_value_by_change_request_id(
            db, change_request_id=change_request.id
        )
        if not change_value:
            raise NotFoundError("Detalle de solicitud de cambio no encontrado.")

        change_request.status = "REJECTED"
        db.commit()
        db.refresh(change_request)
        return ChangeRequestService._to_public(change_request, change_value)

    @staticmethod
    def list_my_requests(db: Session, *, current_user: User) -> list[dict]:
        """Lista solicitudes creadas por el usuario autenticado."""
        requests = ChangeRequestRepository.list_by_created_by(db, created_by=current_user.username)
        data: list[dict] = []
        for req in requests:
            req_value = ChangeRequestRepository.get_value_by_change_request_id(
                db, change_request_id=req.id
            )
            if req_value:
                data.append(ChangeRequestService._to_public(req, req_value))
        return data

    @staticmethod
    def list_pending_by_scenario(
        db: Session, *, scenario_id: int, current_user: User
    ) -> list[dict]:
        """Lista solicitudes pendientes de un escenario administrable."""
        if not ChangeRequestService._can_manage_scenario(
            db, scenario_id=scenario_id, current_user=current_user
        ):
            raise ForbiddenError("No tienes permisos para consultar pendientes en este escenario.")

        requests = ChangeRequestRepository.list_pending_by_scenario(db, scenario_id=scenario_id)
        data: list[dict] = []
        for req in requests:
            req_value = ChangeRequestRepository.get_value_by_change_request_id(
                db, change_request_id=req.id
            )
            if req_value:
                data.append(ChangeRequestService._to_public(req, req_value))
        return data


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Ejecutar workflow de gobernanza de cambios para `parameter_value`.
#
# Posibles mejoras:
# - Añadir estado `CANCELLED` y comentarios de revisión.
# - Incluir versionado optimista para evitar sobrescrituras silenciosas.
#
# Riesgos en producción:
# - Aprobaciones concurrentes sobre el mismo `parameter_value` pueden competir;
#   conviene evaluar locking explícito en escenarios de alta concurrencia.
#
# Escalabilidad:
# - I/O-bound; puede requerir paginación en listados si crece el histórico.
