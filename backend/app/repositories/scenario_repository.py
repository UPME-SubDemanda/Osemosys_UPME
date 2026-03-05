"""Repositorio para escenarios y permisos."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import Scenario, ScenarioPermission


class ScenarioRepository:
    """Consultas de persistencia para dominio de escenarios."""

    @staticmethod
    def get_paginated_accessible(
        db: Session,
        *,
        current_username: str,
        current_user_id: uuid.UUID,
        busqueda: str | None,
        row_offset: int,
        limit: int,
    ) -> tuple[list[Scenario], int]:
        """Retorna escenarios accesibles para un usuario.

        Incluye ownership y permisos explícitos por `ScenarioPermission`.
        Excluye escenarios plantilla del listado operativo.
        """
        base_join = ScenarioPermission

        where_clause = or_(
            Scenario.owner == current_username,
            ScenarioPermission.user_id == current_user_id,
        )
        where_clause = and_(where_clause, Scenario.is_template.is_(False))
        if busqueda:
            where_clause = and_(where_clause, Scenario.name.ilike(f"%{busqueda}%"))

        total_stmt = (
            select(func.count(func.distinct(Scenario.id)))
            .select_from(Scenario)
            .outerjoin(base_join, base_join.id_scenario == Scenario.id)
            .where(where_clause)
        )
        total = int(db.scalar(total_stmt) or 0)

        items_stmt = (
            select(Scenario)
            .outerjoin(base_join, base_join.id_scenario == Scenario.id)
            .where(where_clause)
            .distinct()
            .order_by(Scenario.created_at.desc())
            .offset(row_offset)
            .limit(limit)
        )
        items = db.execute(items_stmt).scalars().all()
        return list(items), total

    @staticmethod
    def get_by_id(db: Session, scenario_id: int) -> Scenario | None:
        """Obtiene escenario por id."""
        return db.get(Scenario, scenario_id)

    @staticmethod
    def create(db: Session, *, name: str, description: str | None, owner: str, edit_policy: str) -> Scenario:
        """Crea escenario no-plantilla por defecto."""
        obj = Scenario(
            name=name,
            description=description,
            owner=owner,
            edit_policy=edit_policy,
            is_template=False,
        )
        db.add(obj)
        return obj

    @staticmethod
    def get_template_scenario(db: Session) -> Scenario | None:
        """Obtiene la plantilla más reciente disponible."""
        stmt = (
            select(Scenario)
            .where(Scenario.is_template.is_(True))
            .order_by(Scenario.created_at.desc())
            .limit(1)
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_permission_for_user(
        db: Session,
        *,
        scenario_id: int,
        user_id: uuid.UUID,
    ) -> ScenarioPermission | None:
        """Obtiene permiso de escenario para usuario específico."""
        stmt = select(ScenarioPermission).where(
            and_(
                ScenarioPermission.id_scenario == scenario_id,
                ScenarioPermission.user_id == user_id,
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_permission_by_identifier(
        db: Session,
        *,
        scenario_id: int,
        user_identifier: str,
    ) -> ScenarioPermission | None:
        """Obtiene permiso por identificador externo/interno."""
        stmt = select(ScenarioPermission).where(
            and_(
                ScenarioPermission.id_scenario == scenario_id,
                ScenarioPermission.user_identifier == user_identifier,
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_permissions(db: Session, *, scenario_id: int) -> list[ScenarioPermission]:
        """Lista permisos de un escenario ordenados por id."""
        stmt = (
            select(ScenarioPermission)
            .where(ScenarioPermission.id_scenario == scenario_id)
            .order_by(ScenarioPermission.id.asc())
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def add_permission(
        db: Session,
        *,
        scenario_id: int,
        user_identifier: str,
        user_id: uuid.UUID | None,
        can_edit_direct: bool,
        can_propose: bool,
        can_manage_values: bool,
    ) -> ScenarioPermission:
        """Inserta nuevo permiso de escenario."""
        perm = ScenarioPermission(
            id_scenario=scenario_id,
            user_identifier=user_identifier,
            user_id=user_id,
            can_edit_direct=can_edit_direct,
            can_propose=can_propose,
            can_manage_values=can_manage_values,
        )
        db.add(perm)
        return perm

    @staticmethod
    def list_parameter_defaults(db: Session) -> list:
        """Lista todos los ParameterValue (defaults globales, sin escenario)."""
        from app.models import ParameterValue
        stmt = select(ParameterValue)
        return list(db.execute(stmt).scalars().all())


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Centralizar consultas SQL de escenarios/permisos sin lógica de negocio.
#
# Posibles mejoras:
# - Agregar eager loading selectivo cuando se requieran relaciones frecuentes.
# - Evaluar keyset pagination para listados muy grandes.
#
# Riesgos en producción:
# - Uso de `distinct + outerjoin` puede penalizar bajo alta cardinalidad.
#
# Escalabilidad:
# - I/O-bound, sensible al tamaño de `scenario_permission`.

