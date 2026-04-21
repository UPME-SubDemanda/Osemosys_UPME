"""Repositorio para escenarios y permisos."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models import Scenario, ScenarioPermission, ScenarioTag


class ScenarioRepository:
    """Consultas de persistencia para dominio de escenarios."""

    @staticmethod
    def get_paginated_accessible(
        db: Session,
        *,
        current_username: str,
        busqueda: str | None,
        owner: str | None,
        edit_policy: str | None,
        permission_scope: str | None,
        row_offset: int,
        limit: int,
    ) -> tuple[list[tuple[Scenario, str | None]], int]:
        """Retorna escenarios accesibles para un usuario.

        Regla de lectura:
        - el owner siempre ve sus escenarios;
        - usuarios ajenos solo ven escenarios `OPEN` o `RESTRICTED`;
        - escenarios plantilla no aparecen en el listado operativo.
        """
        base_scenario = aliased(Scenario)
        scenario_tag_alias = aliased(ScenarioTag)

        readable_clause = or_(
            Scenario.owner == current_username,
            and_(
                Scenario.owner != current_username,
                Scenario.edit_policy.in_(("OPEN", "RESTRICTED")),
            ),
        )
        where_clause = and_(readable_clause, Scenario.is_template.is_(False))
        if busqueda:
            term = f"%{busqueda}%"
            where_clause = and_(
                where_clause,
                or_(
                    Scenario.name.ilike(term),
                    Scenario.description.ilike(term),
                    Scenario.owner.ilike(term),
                ),
            )
        if owner:
            where_clause = and_(where_clause, Scenario.owner == owner)
        if edit_policy:
            where_clause = and_(where_clause, Scenario.edit_policy == edit_policy)
        if permission_scope == "mine":
            where_clause = and_(where_clause, Scenario.owner == current_username)
        elif permission_scope == "editable":
            where_clause = and_(
                where_clause,
                or_(Scenario.owner == current_username, Scenario.edit_policy == "OPEN"),
            )
        elif permission_scope == "readonly":
            where_clause = and_(
                where_clause,
                Scenario.owner != current_username,
                Scenario.edit_policy == "RESTRICTED",
            )

        total_stmt = (
            select(func.count())
            .select_from(Scenario)
            .where(where_clause)
        )
        total = int(db.scalar(total_stmt) or 0)

        items_stmt = (
            select(Scenario, base_scenario.name.label("base_scenario_name"))
            .outerjoin(base_scenario, base_scenario.id == Scenario.base_scenario_id)
            .outerjoin(scenario_tag_alias, scenario_tag_alias.id == Scenario.tag_id)
            .where(where_clause)
            .order_by(
                Scenario.tag_id.is_(None).asc(),
                scenario_tag_alias.sort_order.asc().nulls_last(),
                Scenario.created_at.desc(),
                Scenario.id.desc(),
            )
            .offset(row_offset)
            .limit(limit)
        )
        items = db.execute(items_stmt).all()
        return [(row[0], row.base_scenario_name) for row in items], total

    @staticmethod
    def get_by_id(db: Session, scenario_id: int) -> Scenario | None:
        """Obtiene escenario por id."""
        return db.get(Scenario, scenario_id)

    @staticmethod
    def get_by_id_with_base_name(db: Session, scenario_id: int) -> tuple[Scenario | None, str | None]:
        """Obtiene escenario por id junto con el nombre del escenario padre."""
        base_scenario = aliased(Scenario)
        stmt = (
            select(Scenario, base_scenario.name.label("base_scenario_name"))
            .outerjoin(base_scenario, base_scenario.id == Scenario.base_scenario_id)
            .where(Scenario.id == scenario_id)
        )
        row = db.execute(stmt).one_or_none()
        if row is None:
            return None, None
        return row[0], row.base_scenario_name

    @staticmethod
    def create(
        db: Session,
        *,
        name: str,
        description: str | None,
        owner: str,
        edit_policy: str,
        simulation_type: str = "NATIONAL",
        processing_mode: str = "STANDARD",
    ) -> Scenario:
        """Crea escenario no-plantilla por defecto."""
        obj = Scenario(
            name=name,
            description=description,
            owner=owner,
            edit_policy=edit_policy,
            simulation_type=simulation_type,
            processing_mode=processing_mode,
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
