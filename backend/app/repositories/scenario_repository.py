"""Repositorio para escenarios y permisos."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models import (
    Scenario,
    ScenarioPermission,
    ScenarioTag,
    ScenarioTagCategory,
    ScenarioTagLink,
)


class ScenarioRepository:
    """Consultas de persistencia para dominio de escenarios."""

    @staticmethod
    def _build_visibility_clause(
        *, current_username: str, include_private: bool
    ):
        """Clausula SQL de visibilidad de escenarios para el usuario actual."""
        if include_private:
            readable = None
        else:
            readable = or_(
                Scenario.owner == current_username,
                and_(
                    Scenario.owner != current_username,
                    Scenario.edit_policy.in_(("OPEN", "RESTRICTED")),
                ),
            )
        clause = Scenario.is_template.is_(False)
        if readable is not None:
            clause = and_(readable, clause)
        return clause

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
        include_private: bool = False,
        owners: list[str] | None = None,
        edit_policies: list[str] | None = None,
        simulation_types: list[str] | None = None,
        tag_ids: list[int] | None = None,
    ) -> tuple[list[tuple[Scenario, str | None]], int]:
        """Retorna escenarios accesibles para un usuario.

        Regla de lectura:
        - el owner siempre ve sus escenarios;
        - usuarios ajenos solo ven escenarios `OPEN` o `RESTRICTED`;
        - si ``include_private=True`` (reservado a `can_manage_scenarios`),
          se muestran también escenarios `OWNER_ONLY` de otros usuarios;
        - escenarios plantilla no aparecen en el listado operativo.
        """
        base_scenario = aliased(Scenario)

        where_clause = ScenarioRepository._build_visibility_clause(
            current_username=current_username, include_private=include_private
        )
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
        # Filtros multiselect (AND entre columnas, IN dentro de cada columna)
        if owners:
            where_clause = and_(where_clause, Scenario.owner.in_(owners))
        if edit_policies:
            where_clause = and_(
                where_clause, Scenario.edit_policy.in_(edit_policies)
            )
        if simulation_types:
            where_clause = and_(
                where_clause, Scenario.simulation_type.in_(simulation_types)
            )
        if tag_ids:
            # Escenarios que tengan al menos un tag en tag_ids (semántica: OR dentro del filtro)
            where_clause = and_(
                where_clause,
                Scenario.id.in_(
                    select(ScenarioTagLink.scenario_id).where(
                        ScenarioTagLink.tag_id.in_(tag_ids)
                    )
                ),
            )
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

        # Subquery: "primary tag hierarchy" por escenario (menor hierarchy_level,
        # luego menor sort_order de categoría). Se usa solo para ordenar; los tags
        # completos se cargan aparte en ScenarioService.list.
        primary_hier_subq = (
            select(
                ScenarioTagLink.scenario_id.label("sid"),
                func.min(ScenarioTagCategory.hierarchy_level).label("min_hier"),
            )
            .select_from(ScenarioTagLink)
            .join(ScenarioTag, ScenarioTag.id == ScenarioTagLink.tag_id)
            .join(ScenarioTagCategory, ScenarioTagCategory.id == ScenarioTag.category_id)
            .group_by(ScenarioTagLink.scenario_id)
            .subquery()
        )

        items_stmt = (
            select(Scenario, base_scenario.name.label("base_scenario_name"))
            .outerjoin(base_scenario, base_scenario.id == Scenario.base_scenario_id)
            .outerjoin(primary_hier_subq, primary_hier_subq.c.sid == Scenario.id)
            .where(where_clause)
            .order_by(
                primary_hier_subq.c.min_hier.is_(None).asc(),
                primary_hier_subq.c.min_hier.asc().nulls_last(),
                Scenario.created_at.desc(),
                Scenario.id.desc(),
            )
            .offset(row_offset)
            .limit(limit)
        )
        items = db.execute(items_stmt).all()
        return [(row[0], row.base_scenario_name) for row in items], total

    @staticmethod
    def get_facets(
        db: Session,
        *,
        current_username: str,
        include_private: bool = False,
    ) -> dict:
        """Valores distintos para construir filtros multiselect en el listado.

        Respeta la visibilidad del usuario (con ``include_private`` reservado a
        administradores). Devuelve owners, edit_policies, simulation_types y
        tags accesibles. No narrowed por filtros activos — son facetas
        completas para que el usuario vea todas las opciones posibles.
        """
        base_where = ScenarioRepository._build_visibility_clause(
            current_username=current_username, include_private=include_private
        )

        owners = sorted(
            {
                str(v)
                for v in db.execute(
                    select(Scenario.owner).where(base_where).distinct()
                ).scalars().all()
                if v
            }
        )
        edit_policies = sorted(
            {
                str(v)
                for v in db.execute(
                    select(Scenario.edit_policy).where(base_where).distinct()
                ).scalars().all()
                if v
            }
        )
        simulation_types = sorted(
            {
                str(v)
                for v in db.execute(
                    select(Scenario.simulation_type).where(base_where).distinct()
                ).scalars().all()
                if v
            }
        )

        # Tags: los que están asignados a escenarios visibles.
        # Usamos subquery con DISTINCT de tag_id para evitar filas duplicadas
        # por múltiples scenario_tag_link; luego join para traer metadatos.
        visible_tag_ids_subq = (
            select(ScenarioTagLink.tag_id)
            .join(Scenario, Scenario.id == ScenarioTagLink.scenario_id)
            .where(base_where)
            .distinct()
            .subquery()
        )
        tag_rows = db.execute(
            select(
                ScenarioTag.id,
                ScenarioTag.name,
                ScenarioTag.color,
                ScenarioTag.category_id,
                ScenarioTagCategory.name.label("category_name"),
                ScenarioTagCategory.hierarchy_level.label("hierarchy_level"),
            )
            .join(
                visible_tag_ids_subq,
                visible_tag_ids_subq.c.tag_id == ScenarioTag.id,
            )
            .join(
                ScenarioTagCategory,
                ScenarioTagCategory.id == ScenarioTag.category_id,
            )
            .order_by(
                ScenarioTagCategory.hierarchy_level.asc(),
                ScenarioTag.sort_order.asc(),
                ScenarioTag.name.asc(),
            )
        ).all()
        tags = [
            {
                "id": int(r.id),
                "name": r.name,
                "color": r.color,
                "category_id": int(r.category_id),
                "category_name": r.category_name,
                "hierarchy_level": int(r.hierarchy_level),
            }
            for r in tag_rows
        ]

        return {
            "owners": owners,
            "edit_policies": edit_policies,
            "simulation_types": simulation_types,
            "tags": tags,
        }

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
