"""Servicio de negocio para escenarios y control de permisos.

Este módulo centraliza:
- creación de escenarios (incluyendo plantillas),
- poblado de osemosys_param_value desde defaults (parameter_value),
- administración de permisos por usuario.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import and_, cast, func, or_, select, String, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.dialect import osemosys_table
from app.models import (
    Emission,
    Fuel,
    OsemosysParamValue,
    Parameter,
    Region,
    Scenario,
    ScenarioPermission,
    Solver,
    Technology,
    UdcSet,
    User,
)
from app.repositories.scenario_repository import ScenarioRepository
from app.services.pagination import build_meta, normalize_pagination
from app.services.user_service import UserService

logger = logging.getLogger(__name__)


CLONE_BATCH_SIZE = 500_000


class ScenarioService:
    """Reglas de negocio para gestión de escenarios OSEMOSYS."""

    @staticmethod
    def _get_permission(db: Session, *, scenario_id: int, current_user: User) -> ScenarioPermission | None:
        permission = ScenarioRepository.get_permission_for_user(
            db, scenario_id=scenario_id, user_id=current_user.id
        )
        if permission is None:
            permission = ScenarioRepository.get_permission_by_identifier(
                db, scenario_id=scenario_id, user_identifier=f"user:{current_user.username}"
            )
        return permission

    @staticmethod
    def _can_view_scenario(scenario: Scenario, *, current_user: User) -> bool:
        if scenario.owner == current_user.username:
            return True
        return scenario.edit_policy in {"OPEN", "RESTRICTED"}

    @staticmethod
    def _effective_access(
        db: Session,
        *,
        scenario: Scenario,
        current_user: User,
    ) -> dict[str, bool]:
        if scenario.owner == current_user.username:
            return {
                "can_view": True,
                "is_owner": True,
                "can_edit_direct": True,
                "can_propose": True,
                "can_manage_values": True,
            }

        permission = ScenarioService._get_permission(
            db, scenario_id=int(scenario.id), current_user=current_user
        )

        if scenario.edit_policy == "OPEN":
            return {
                "can_view": True,
                "is_owner": False,
                "can_edit_direct": False,
                "can_propose": True,
                "can_manage_values": True,
            }

        if scenario.edit_policy == "RESTRICTED":
            return {
                "can_view": True,
                "is_owner": False,
                "can_edit_direct": bool(permission and permission.can_edit_direct),
                "can_propose": bool(permission and permission.can_propose),
                "can_manage_values": bool(
                    permission and (permission.can_manage_values or permission.can_edit_direct)
                ),
            }

        return {
            "can_view": False,
            "is_owner": False,
            "can_edit_direct": False,
            "can_propose": False,
            "can_manage_values": False,
        }

    @staticmethod
    def _to_public(
        db: Session,
        *,
        scenario: Scenario,
        current_user: User,
        base_scenario_name: str | None,
    ) -> dict:
        return {
            "id": int(scenario.id),
            "name": scenario.name,
            "description": scenario.description,
            "owner": scenario.owner,
            "base_scenario_id": int(scenario.base_scenario_id) if scenario.base_scenario_id is not None else None,
            "base_scenario_name": base_scenario_name,
            "changed_param_names": list(scenario.changed_param_names or []),
            "edit_policy": scenario.edit_policy,
            "is_template": bool(scenario.is_template),
            "created_at": scenario.created_at,
            "effective_access": ScenarioService._effective_access(
                db, scenario=scenario, current_user=current_user
            ),
        }

    @staticmethod
    def _track_changed_params(
        scenario: Scenario,
        *,
        param_names: list[str] | tuple[str, ...] | set[str],
    ) -> None:
        """Registra nombres de parámetros modificados para escenarios derivados."""
        if scenario.base_scenario_id is None:
            return
        existing = list(scenario.changed_param_names or [])
        seen = {name for name in existing if isinstance(name, str)}
        for raw_name in param_names:
            clean_name = str(raw_name or "").strip()
            if not clean_name or clean_name in seen:
                continue
            existing.append(clean_name)
            seen.add(clean_name)
        scenario.changed_param_names = existing

    @staticmethod
    def _clone_data_batched(
        db: Session,
        *,
        source_id: int,
        new_id: int,
        batch_size: int = CLONE_BATCH_SIZE,
        on_batch: callable | None = None,
    ) -> int:
        """Copia osemosys_param_value por lotes usando paginación por cursor.

        Cada lote hace INSERT...SELECT de hasta *batch_size* filas y luego
        COMMIT, evitando transacciones gigantes que saturen la BD o causen
        timeouts en el cliente.
        """
        total = 0
        cursor = 0
        osemosys_param_value_table = osemosys_table("osemosys_param_value")

        while True:
            max_id_in_batch = db.execute(
                text(f"""
                    SELECT MAX(id) FROM (
                        SELECT id FROM {osemosys_param_value_table}
                        WHERE id_scenario = :src AND id > :cursor
                        ORDER BY id
                        LIMIT :batch
                    ) t
                """),
                {"src": source_id, "cursor": cursor, "batch": batch_size},
            ).scalar()

            if max_id_in_batch is None:
                break

            cnt = db.execute(
                text(f"""
                    INSERT INTO {osemosys_param_value_table}
                        (id_scenario, param_name,
                         id_region, id_technology, id_fuel, id_emission,
                         id_timeslice, id_mode_of_operation,
                         id_season, id_daytype, id_dailytimebracket,
                         id_storage_set, id_udc_set, year, value)
                    SELECT
                        :new_id, param_name,
                        id_region, id_technology, id_fuel, id_emission,
                        id_timeslice, id_mode_of_operation,
                        id_season, id_daytype, id_dailytimebracket,
                        id_storage_set, id_udc_set, year, value
                    FROM {osemosys_param_value_table}
                    WHERE id_scenario = :src
                      AND id > :cursor
                      AND id <= :max_id
                """),
                {
                    "new_id": new_id,
                    "src": source_id,
                    "cursor": cursor,
                    "max_id": max_id_in_batch,
                },
            ).rowcount

            db.commit()
            total += cnt
            cursor = max_id_in_batch
            logger.info(
                "Lote clonado: %d filas (acumulado: %d)", cnt, total,
            )
            if on_batch is not None:
                on_batch(cnt, total)

        return total

    @staticmethod
    def _populate_osemosys_from_defaults(db: Session, *, target_scenario_id: int) -> int:
        """Copia los defaults de parameter_value a osemosys_param_value para un escenario.

        Hace INSERT...SELECT con JOIN a parameter para resolver param_name.
        Las dimensiones que parameter_value no tiene (timeslice, mode, season, etc.)
        quedan NULL y se completan después por run_notebook_preprocess.
        """
        osemosys_param_value_table = osemosys_table("osemosys_param_value")
        parameter_value_table = osemosys_table("parameter_value")
        parameter_table = osemosys_table("parameter")
        parameter_storage_table = osemosys_table("parameter_storage")
        result = db.execute(
            text(f"""
                INSERT INTO {osemosys_param_value_table}
                    (id_scenario, param_name,
                     id_region, id_technology, id_fuel, id_emission,
                     id_timeslice, id_mode_of_operation,
                     id_season, id_daytype, id_dailytimebracket,
                     id_storage_set, id_udc_set, year, value)
                SELECT
                    :target_id, p.name,
                    pv.id_region, pv.id_technology, pv.id_fuel, pv.id_emission,
                    ps.timesline, NULL,
                    ps.season, ps.daytype, ps.dailytimebracket,
                    ps.id_storage_set, NULL, pv.year, pv.value
                FROM {parameter_value_table} pv
                JOIN {parameter_table} p ON pv.id_parameter = p.id
                LEFT JOIN {parameter_storage_table} ps ON ps.id_parameter_value = pv.id
            """),
            {"target_id": target_scenario_id},
        )
        return result.rowcount

    @staticmethod
    def list(
        db: Session,
        *,
        current_user: User,
        busqueda: str | None,
        owner: str | None,
        edit_policy: str | None,
        permission_scope: str | None,
        cantidad: int | None,
        offset: int | None,
    ) -> dict:
        """Lista escenarios accesibles para el usuario autenticado."""
        page, page_size, row_offset = normalize_pagination(offset, cantidad)
        items, total = ScenarioRepository.get_paginated_accessible(
            db,
            current_username=current_user.username,
            busqueda=busqueda,
            owner=owner,
            edit_policy=edit_policy,
            permission_scope=permission_scope,
            row_offset=row_offset,
            limit=page_size,
        )
        meta = build_meta(page, page_size, total, busqueda)
        return {
            "data": [
                ScenarioService._to_public(
                    db,
                    scenario=scenario,
                    current_user=current_user,
                    base_scenario_name=base_scenario_name,
                )
                for scenario, base_scenario_name in items
            ],
            "meta": meta,
        }

    @staticmethod
    def get_public(db: Session, *, scenario_id: int, current_user: User) -> dict:
        """Retorna un escenario visible al usuario autenticado."""
        scenario, base_scenario_name = ScenarioRepository.get_by_id_with_base_name(db, scenario_id)
        if scenario is None:
            raise NotFoundError("Escenario no encontrado.")
        if not ScenarioService._can_view_scenario(scenario, current_user=current_user):
            raise ForbiddenError("No tienes acceso a este escenario.")
        return ScenarioService._to_public(
            db,
            scenario=scenario,
            current_user=current_user,
            base_scenario_name=base_scenario_name,
        )

    @staticmethod
    def create(
        db: Session,
        *,
        current_user: User,
        name: str,
        description: str | None,
        edit_policy: str,
        is_template: bool,
        skip_populate_defaults: bool = False,
    ):
        """Crea escenario y configura permisos iniciales del creador.

        Flujo:
            1. Inserta escenario.
            2. Crea permiso total para owner.
            3. Si no es plantilla, copia defaults de parameter_value a osemosys_param_value
               y ejecuta preprocesamiento (completar matrices, UDC, emisiones).
            4. Confirma transacción.

        Args:
            skip_populate_defaults: Si True, no copia defaults ni ejecuta preprocess.
                Usado cuando el flujo import-excel poblará osemosys_param_value directamente.
        """
        scenario = Scenario(
            name=name,
            description=description,
            owner=current_user.username,
            edit_policy=edit_policy,
            is_template=is_template,
        )
        db.add(scenario)
        db.flush()

        ScenarioRepository.add_permission(
            db,
            scenario_id=scenario.id,
            user_identifier=f"user:{current_user.username}",
            user_id=current_user.id,
            can_edit_direct=True,
            can_propose=True,
            can_manage_values=True,
        )

        if not is_template and not skip_populate_defaults:
            count = ScenarioService._populate_osemosys_from_defaults(
                db, target_scenario_id=scenario.id
            )
            logger.info("Escenario %s: %d defaults copiados a osemosys_param_value", scenario.id, count)
            if count > 0:
                from app.services.sand_notebook_preprocess import run_notebook_preprocess
                preprocess_stats = run_notebook_preprocess(
                    db,
                    int(scenario.id),
                    filter_by_sets=True,
                    complete_matrices=False,
                    emission_ratios_at_input=False,
                    generate_udc_matrices=False,
                )
                logger.info("Escenario %s: preprocess completado %s", scenario.id, preprocess_stats)

        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("No se pudo crear el escenario (posible duplicado o conflicto).") from e
        db.refresh(scenario)
        return scenario

    @staticmethod
    def clone(
        db: Session,
        *,
        source_scenario_id: int,
        current_user: User,
        name: str,
        description: str | None,
        edit_policy: str,
    ) -> dict:
        """Clona un escenario existente con todos sus OsemosysParamValue.

        El usuario debe tener acceso al escenario origen. El nuevo escenario
        pertenece al usuario actual. Los datos se copian con INSERT...SELECT
        para máxima eficiencia.
        """
        source = ScenarioService._require_access(
            db, scenario_id=source_scenario_id, current_user=current_user,
        )

        new_scenario = Scenario(
            name=name,
            description=description,
            owner=current_user.username,
            base_scenario_id=source.id,
            changed_param_names=[],
            edit_policy=edit_policy,
            is_template=False,
            udc_config=source.udc_config,
        )
        db.add(new_scenario)
        db.flush()

        ScenarioRepository.add_permission(
            db,
            scenario_id=new_scenario.id,
            user_identifier=f"user:{current_user.username}",
            user_id=current_user.id,
            can_edit_direct=True,
            can_propose=True,
            can_manage_values=True,
        )

        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("No se pudo clonar el escenario (posible duplicado o conflicto).") from e

        count = ScenarioService._clone_data_batched(
            db, source_id=source_scenario_id, new_id=new_scenario.id,
        )
        ScenarioService.sync_catalogs_from_scenario_values(db, scenario_id=int(new_scenario.id))
        logger.info(
            "Escenario %s clonado desde %s: %d filas copiadas",
            new_scenario.id, source_scenario_id, count,
        )

        db.refresh(new_scenario)
        return ScenarioService._to_public(
            db,
            scenario=new_scenario,
            current_user=current_user,
            base_scenario_name=source.name,
        )

    @staticmethod
    def _require_admin(db: Session, *, scenario_id: int, current_user: User):
        """Valida que usuario tenga capacidad administrativa del escenario."""
        scenario = ScenarioRepository.get_by_id(db, scenario_id)
        if not scenario:
            raise NotFoundError("Escenario no encontrado.")

        if scenario.owner == current_user.username:
            return scenario

        perm = ScenarioRepository.get_permission_for_user(db, scenario_id=scenario_id, user_id=current_user.id)
        if not perm or not perm.can_edit_direct:
            raise ForbiddenError("No tienes permisos para administrar este escenario.")
        return scenario

    @staticmethod
    def _require_access(db: Session, *, scenario_id: int, current_user: User):
        """Valida acceso básico al escenario según reglas de visibilidad."""
        scenario = ScenarioRepository.get_by_id(db, scenario_id)
        if not scenario:
            raise NotFoundError("Escenario no encontrado.")
        if ScenarioService._can_view_scenario(scenario, current_user=current_user):
            return scenario
        raise ForbiddenError("No tienes acceso a este escenario.")

    @staticmethod
    def _require_manage_values(db: Session, *, scenario_id: int, current_user: User):
        """Valida capacidad de edición de valores del escenario."""
        scenario = ScenarioService._require_access(db, scenario_id=scenario_id, current_user=current_user)
        if scenario.owner == current_user.username:
            return scenario
        permission = ScenarioService._get_permission(
            db, scenario_id=scenario_id, current_user=current_user
        )
        if scenario.edit_policy == "OPEN":
            return scenario
        if permission and (permission.can_manage_values or permission.can_edit_direct):
            return scenario
        raise ForbiddenError("No tienes permisos para editar valores de este escenario.")

    @staticmethod
    def _resolve_or_create_catalog_name(db: Session, *, model, name: str | None, label: str) -> int | None:
        cleaned = (name or "").strip()
        if not cleaned:
            return None
        obj = db.execute(select(model).where(model.name == cleaned)).scalar_one_or_none()
        if obj is None:
            obj = model(name=cleaned)
            db.add(obj)
            db.flush()
        # Si el catálogo usa soft delete, se reactiva al reutilizarse desde escenario.
        if hasattr(obj, "is_active") and getattr(obj, "is_active") is False:
            setattr(obj, "is_active", True)
            db.flush()
        return int(obj.id)

    @staticmethod
    def _ensure_parameter_exists(db: Session, *, param_name: str) -> str:
        cleaned = str(param_name or "").strip()
        if not cleaned:
            raise ConflictError("El parámetro es obligatorio.")
        obj = db.execute(select(Parameter).where(Parameter.name == cleaned)).scalar_one_or_none()
        if obj is None:
            obj = Parameter(name=cleaned, is_active=True)
            db.add(obj)
            db.flush()
        elif obj.is_active is False:
            obj.is_active = True
            db.flush()
        return cleaned

    @staticmethod
    def _ensure_solver_if_provided(db: Session, *, solver_name: str | None) -> None:
        cleaned = (solver_name or "").strip()
        if not cleaned:
            return
        ScenarioService._resolve_or_create_catalog_name(
            db, model=Solver, name=cleaned, label="Solver"
        )

    @staticmethod
    def sync_catalogs_from_scenario_values(db: Session, *, scenario_id: int) -> None:
        """Sincroniza catálogos globales a partir de valores del escenario.

        - Garantiza que `param_name` de `osemosys_param_value` exista y esté activo en `parameter`.
        - Reactiva catálogos referenciados por ID (region, technology, fuel, emission).
        """
        # 1) Parámetros por nombre desde osemosys_param_value
        param_names = (
            db.execute(
                select(OsemosysParamValue.param_name)
                .where(OsemosysParamValue.id_scenario == scenario_id)
                .distinct()
            )
            .scalars()
            .all()
        )
        for raw_name in param_names:
            clean_name = str(raw_name or "").strip()
            if not clean_name:
                continue
            ScenarioService._ensure_parameter_exists(db, param_name=clean_name)

        # 2) Reactivar entidades referenciadas por IDs del escenario
        id_regions = (
            db.execute(
                select(OsemosysParamValue.id_region)
                .where(
                    OsemosysParamValue.id_scenario == scenario_id,
                    OsemosysParamValue.id_region.is_not(None),
                )
                .distinct()
            )
            .scalars()
            .all()
        )
        id_technologies = (
            db.execute(
                select(OsemosysParamValue.id_technology)
                .where(
                    OsemosysParamValue.id_scenario == scenario_id,
                    OsemosysParamValue.id_technology.is_not(None),
                )
                .distinct()
            )
            .scalars()
            .all()
        )
        id_fuels = (
            db.execute(
                select(OsemosysParamValue.id_fuel)
                .where(
                    OsemosysParamValue.id_scenario == scenario_id,
                    OsemosysParamValue.id_fuel.is_not(None),
                )
                .distinct()
            )
            .scalars()
            .all()
        )
        id_emissions = (
            db.execute(
                select(OsemosysParamValue.id_emission)
                .where(
                    OsemosysParamValue.id_scenario == scenario_id,
                    OsemosysParamValue.id_emission.is_not(None),
                )
                .distinct()
            )
            .scalars()
            .all()
        )

        for model, ids in (
            (Region, id_regions),
            (Technology, id_technologies),
            (Fuel, id_fuels),
            (Emission, id_emissions),
        ):
            if not ids:
                continue
            objects = (
                db.execute(select(model).where(model.id.in_(list(ids))))
                .scalars()
                .all()
            )
            for obj in objects:
                if hasattr(obj, "is_active") and getattr(obj, "is_active") is False:
                    setattr(obj, "is_active", True)
            db.flush()

    @staticmethod
    def list_permissions(db: Session, *, scenario_id: int, current_user: User):
        """Lista permisos del escenario si el usuario es administrador."""
        ScenarioService._require_admin(db, scenario_id=scenario_id, current_user=current_user)
        return ScenarioRepository.list_permissions(db, scenario_id=scenario_id)

    @staticmethod
    def upsert_permission(
        db: Session,
        *,
        scenario_id: int,
        current_user: User,
        user_id: uuid.UUID | None,
        user_identifier: str | None,
        can_edit_direct: bool,
        can_propose: bool,
        can_manage_values: bool,
    ):
        """Crea o actualiza permiso de acceso para un usuario del escenario."""
        ScenarioService._require_admin(db, scenario_id=scenario_id, current_user=current_user)

        identifier = (user_identifier or "").strip()
        if not identifier:
            identifier = f"user:{user_id}"

        resolved_user_id = user_id
        if resolved_user_id is None and identifier.startswith("user:"):
            username = identifier.split(":", maxsplit=1)[1].strip()
            if username:
                target = UserService.get_by_username(db, username=username)
                if target:
                    resolved_user_id = target.id

        perm = ScenarioRepository.get_permission_by_identifier(db, scenario_id=scenario_id, user_identifier=identifier)
        if perm:
            if resolved_user_id is not None:
                perm.user_id = resolved_user_id
            perm.can_edit_direct = can_edit_direct
            perm.can_propose = can_propose
            perm.can_manage_values = can_manage_values
        else:
            perm = ScenarioRepository.add_permission(
                db,
                scenario_id=scenario_id,
                user_identifier=identifier,
                user_id=resolved_user_id,
                can_edit_direct=can_edit_direct,
                can_propose=can_propose,
                can_manage_values=can_manage_values,
            )
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("No se pudo crear/actualizar el permiso (posible conflicto).") from e
        db.refresh(perm)
        return perm

    @staticmethod
    def update_metadata(
        db: Session,
        *,
        scenario_id: int,
        current_user: User,
        payload: dict,
    ) -> dict:
        """Actualiza nombre, descripción y/o política del escenario."""
        scenario = ScenarioService._require_admin(db, scenario_id=scenario_id, current_user=current_user)
        new_name = payload.get("name")
        new_description = payload.get("description")
        new_edit_policy = payload.get("edit_policy")
        touched = False

        if new_name is not None:
            clean_name = str(new_name).strip()
            if not clean_name:
                raise ConflictError("El nombre del escenario es obligatorio.")
            if clean_name != scenario.name:
                scenario.name = clean_name
                touched = True

        if new_description is not None:
            clean_description = str(new_description).strip() or None
            if clean_description != scenario.description:
                scenario.description = clean_description
                touched = True

        if new_edit_policy is not None and new_edit_policy != scenario.edit_policy:
            scenario.edit_policy = str(new_edit_policy)
            touched = True

        if touched:
            try:
                db.commit()
            except IntegrityError as e:
                db.rollback()
                raise ConflictError("No se pudo actualizar el escenario (posible duplicado o conflicto).") from e
            db.refresh(scenario)

        _, base_scenario_name = ScenarioRepository.get_by_id_with_base_name(db, scenario_id)
        return ScenarioService._to_public(
            db,
            scenario=scenario,
            current_user=current_user,
            base_scenario_name=base_scenario_name,
        )

    @staticmethod
    def list_osemosys_summary(db: Session, *, scenario_id: int, current_user: User) -> list[dict]:
        """Retorna resumen agregado por parámetro/año de `osemosys_param_value`."""
        ScenarioService._require_access(db, scenario_id=scenario_id, current_user=current_user)
        rows = db.execute(
            select(
                OsemosysParamValue.param_name.label("param_name"),
                OsemosysParamValue.year.label("year"),
                func.count().label("records"),
                func.sum(OsemosysParamValue.value).label("total_value"),
            )
            .where(OsemosysParamValue.id_scenario == scenario_id)
            .group_by(OsemosysParamValue.param_name, OsemosysParamValue.year)
            .order_by(OsemosysParamValue.param_name.asc(), OsemosysParamValue.year.asc())
        ).all()
        return [
            {
                "param_name": str(r.param_name),
                "year": int(r.year) if r.year is not None else None,
                "records": int(r.records),
                "total_value": float(r.total_value or 0.0),
            }
            for r in rows
        ]

    @staticmethod
    def list_osemosys_values(
        db: Session,
        *,
        scenario_id: int,
        current_user: User,
        param_name: str | None = None,
        year: int | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict:
        """Paginación server-side de valores OSeMOSYS con búsqueda global.

        Hace LEFT JOIN con tablas de catálogo para resolver nombres y permitir
        búsqueda ILIKE en todas las columnas visibles (parámetro, región,
        tecnología, combustible, emisión, UDC, año, valor).
        """
        ScenarioService._require_access(db, scenario_id=scenario_id, current_user=current_user)

        query = (
            db.query(
                OsemosysParamValue,
                Region.name.label("region_name"),
                Technology.name.label("technology_name"),
                Fuel.name.label("fuel_name"),
                Emission.name.label("emission_name"),
                UdcSet.code.label("udc_name"),
            )
            .outerjoin(Region, OsemosysParamValue.id_region == Region.id)
            .outerjoin(Technology, OsemosysParamValue.id_technology == Technology.id)
            .outerjoin(Fuel, OsemosysParamValue.id_fuel == Fuel.id)
            .outerjoin(Emission, OsemosysParamValue.id_emission == Emission.id)
            .outerjoin(UdcSet, OsemosysParamValue.id_udc_set == UdcSet.id)
            .filter(OsemosysParamValue.id_scenario == scenario_id)
        )

        if param_name and param_name.strip():
            query = query.filter(OsemosysParamValue.param_name.ilike(f"%{param_name.strip()}%"))
        if year is not None:
            query = query.filter(OsemosysParamValue.year == year)

        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    OsemosysParamValue.param_name.ilike(term),
                    Region.name.ilike(term),
                    Technology.name.ilike(term),
                    Fuel.name.ilike(term),
                    Emission.name.ilike(term),
                    UdcSet.code.ilike(term),
                    cast(OsemosysParamValue.year, String).ilike(term),
                    cast(OsemosysParamValue.value, String).ilike(term),
                )
            )

        total = query.count()

        safe_limit = max(1, min(limit, 500))
        safe_offset = max(0, offset)

        rows = (
            query.order_by(
                OsemosysParamValue.param_name.asc(),
                OsemosysParamValue.year.asc(),
                OsemosysParamValue.id.asc(),
            )
            .offset(safe_offset)
            .limit(safe_limit)
            .all()
        )

        items = [
            {
                "id": int(r.OsemosysParamValue.id),
                "id_scenario": int(r.OsemosysParamValue.id_scenario),
                "param_name": str(r.OsemosysParamValue.param_name),
                "region_name": r.region_name,
                "technology_name": r.technology_name,
                "fuel_name": r.fuel_name,
                "emission_name": r.emission_name,
                "udc_name": r.udc_name,
                "year": int(r.OsemosysParamValue.year) if r.OsemosysParamValue.year is not None else None,
                "value": float(r.OsemosysParamValue.value),
            }
            for r in rows
        ]

        return {"items": items, "total": total, "offset": safe_offset, "limit": safe_limit}

    @staticmethod
    def ensure_default_reserve_margin_udc(db: Session, *, scenario_id: int) -> None:
        """Inserta valores UDC por defecto tipo 'RESERVEMARGIN' para un escenario.

        - Solo toca parámetros:
          - UDCMultiplierTotalCapacity
          - UDCConstant
          - UDCTag
        - Es idempotente: si ya existen filas con mismas dimensiones, solo actualiza value.
        """

        # Multiplicadores por tecnología (ejemplo RESERVEMARGIN del notebook).
        udc_multiplier_dict: dict[str, float] = {
            "PWRAFR": -1.0,
            "PWRBGS": -1.0,
            "PWRCOA": -1.0,
            "PWRCOACCS": -1.0,
            "PWRCSP": 0.0,
            "PWRDSL": -1.0,
            "PWRFOIL": -1.0,
            "PWRGEO": -1.0,
            "PWRHYDDAM": -1.0,
            "PWRHYDROR": 0.0,
            "PWRHYDROR_NDC": 0.0,
            "PWRJET": -1.0,
            "PWRLPG": -1.0,
            "PWRNGS_CC": -1.0,
            "PWRNGS_CS": -1.0,
            "PWRNGSCCS": -1.0,
            "PWRNUC": -1.0,
            "PWRSOLRTP": 0.0,
            "PWRSOLRTP_ZNI": 0.0,
            "PWRSOLUGE": 0.0,
            "PWRSOLUGE_BAT": -1.0,
            "PWRSOLUPE": 0.0,
            "PWRSTD": 0.0,
            "PWRWAS": -1.0,
            "PWRWNDOFS_FIX": -1.0,
            "PWRWNDOFS_FLO": -1.0,
            "PWRWNDONS": -1.0,
            "GRDTYDELC": (1.0 / 0.9) * 1.2,
        }

        # UDCSet: RESERVEMARGIN (se crea si no existe).
        udc = db.execute(select(UdcSet).where(UdcSet.code == "RESERVEMARGIN")).scalar_one_or_none()
        if udc is None:
            udc = UdcSet(code="RESERVEMARGIN", description="Reserva de margen de capacidad (default)")
            db.add(udc)
            db.flush()
        udc_id = int(udc.id)

        # Tecnologías presentes en el catálogo que coinciden con el dict.
        tech_rows = (
            db.execute(select(Technology).where(Technology.name.in_(list(udc_multiplier_dict.keys()))))
            .scalars()
            .all()
        )
        tech_map: dict[str, int] = {t.name: int(t.id) for t in tech_rows}

        # Años activos del escenario (si no hay años, no hacemos nada).
        years = (
            db.execute(
                select(OsemosysParamValue.year)
                .where(
                    OsemosysParamValue.id_scenario == scenario_id,
                    OsemosysParamValue.year.is_not(None),
                )
                .distinct()
            )
            .scalars()
            .all()
        )
        year_list = sorted(int(y) for y in years if y is not None)
        if not year_list:
            return

        # Regiones del catálogo: aplicamos a todas; si alguna región no tiene tecnologías,
        # la restricción queda vacía y no afecta el modelo.
        region_ids = [int(r.id) for r in db.execute(select(Region)).scalars().all()]
        if not region_ids:
            return

        def _upsert(
            *,
            param_name: str,
            value: float,
            id_region: int,
            id_technology: int | None,
            year: int,
            id_udc_set: int,
        ) -> None:
            conds = [
                OsemosysParamValue.id_scenario == scenario_id,
                OsemosysParamValue.param_name == param_name,
                OsemosysParamValue.id_region == id_region,
                OsemosysParamValue.id_udc_set == id_udc_set,
                OsemosysParamValue.year == year,
            ]
            if id_technology is None:
                conds.append(OsemosysParamValue.id_technology.is_(None))
            else:
                conds.append(OsemosysParamValue.id_technology == id_technology)

            stmt = select(OsemosysParamValue).where(and_(*conds))
            obj = db.execute(stmt).scalar_one_or_none()
            if obj:
                obj.value = float(value)
                return
            db.add(
                OsemosysParamValue(
                    id_scenario=scenario_id,
                    param_name=param_name,
                    id_region=id_region,
                    id_technology=id_technology,
                    id_udc_set=id_udc_set,
                    year=year,
                    value=float(value),
                )
            )

        for region_id in region_ids:
            for year in year_list:
                # Constante y tag por región/año (<=, constante 0).
                _upsert(
                    param_name="UDCConstant",
                    value=0.0,
                    id_region=region_id,
                    id_technology=None,
                    year=year,
                    id_udc_set=udc_id,
                )
                _upsert(
                    param_name="UDCTag",
                    value=0.0,
                    id_region=region_id,
                    id_technology=None,
                    year=year,
                    id_udc_set=udc_id,
                )
                # Multiplicadores por tecnología.
                for tech_name, mult in udc_multiplier_dict.items():
                    tech_id = tech_map.get(tech_name)
                    if tech_id is None:
                        continue
                    _upsert(
                        param_name="UDCMultiplierTotalCapacity",
                        value=float(mult),
                        id_region=region_id,
                        id_technology=tech_id,
                        year=year,
                        id_udc_set=udc_id,
                    )

        db.commit()

    @staticmethod
    def _osemosys_value_to_public(db: Session, *, value_id: int) -> dict:
        """Devuelve un dict público de un OsemosysParamValue por ID exacto con JOINs."""
        row = (
            db.query(
                OsemosysParamValue,
                Region.name.label("region_name"),
                Technology.name.label("technology_name"),
                Fuel.name.label("fuel_name"),
                Emission.name.label("emission_name"),
                UdcSet.code.label("udc_name"),
            )
            .outerjoin(Region, OsemosysParamValue.id_region == Region.id)
            .outerjoin(Technology, OsemosysParamValue.id_technology == Technology.id)
            .outerjoin(Fuel, OsemosysParamValue.id_fuel == Fuel.id)
            .outerjoin(Emission, OsemosysParamValue.id_emission == Emission.id)
            .outerjoin(UdcSet, OsemosysParamValue.id_udc_set == UdcSet.id)
            .filter(OsemosysParamValue.id == value_id)
            .one()
        )
        return {
            "id": int(row.OsemosysParamValue.id),
            "id_scenario": int(row.OsemosysParamValue.id_scenario),
            "param_name": str(row.OsemosysParamValue.param_name),
            "region_name": row.region_name,
            "technology_name": row.technology_name,
            "fuel_name": row.fuel_name,
            "emission_name": row.emission_name,
            "udc_name": row.udc_name,
            "year": int(row.OsemosysParamValue.year) if row.OsemosysParamValue.year is not None else None,
            "value": float(row.OsemosysParamValue.value),
        }

    @staticmethod
    def create_osemosys_value(
        db: Session,
        *,
        scenario_id: int,
        current_user: User,
        payload: dict,
    ) -> dict:
        """Crea una fila OSeMOSYS en un escenario."""
        scenario = ScenarioService._require_manage_values(
            db, scenario_id=scenario_id, current_user=current_user
        )
        clean_param_name = ScenarioService._ensure_parameter_exists(
            db, param_name=str(payload.get("param_name") or "")
        )
        id_region = ScenarioService._resolve_or_create_catalog_name(
            db, model=Region, name=payload.get("region_name"), label="Región"
        )
        id_technology = ScenarioService._resolve_or_create_catalog_name(
            db, model=Technology, name=payload.get("technology_name"), label="Tecnología"
        )
        id_fuel = ScenarioService._resolve_or_create_catalog_name(
            db, model=Fuel, name=payload.get("fuel_name"), label="Combustible"
        )
        id_emission = ScenarioService._resolve_or_create_catalog_name(
            db, model=Emission, name=payload.get("emission_name"), label="Emisión"
        )
        ScenarioService._ensure_solver_if_provided(db, solver_name=payload.get("solver_name"))
        udc_code = (payload.get("udc_name") or "").strip() or None
        id_udc_set: int | None = None
        if udc_code:
            obj_udc = db.execute(select(UdcSet).where(UdcSet.code == udc_code)).scalar_one_or_none()
            if obj_udc is None:
                raise NotFoundError(f"UDC no encontrado: {udc_code}")
            id_udc_set = int(obj_udc.id)
        obj = OsemosysParamValue(
            id_scenario=scenario_id,
            param_name=clean_param_name,
            id_region=id_region,
            id_technology=id_technology,
            id_fuel=id_fuel,
            id_emission=id_emission,
            id_udc_set=id_udc_set,
            year=payload.get("year"),
            value=float(payload.get("value")),
        )
        db.add(obj)
        ScenarioService._track_changed_params(
            scenario, param_names=[clean_param_name]
        )
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("No se pudo crear el valor OSeMOSYS (posible duplicado de dimensiones).") from e
        db.refresh(obj)
        return ScenarioService._osemosys_value_to_public(db, value_id=int(obj.id))

    @staticmethod
    def update_osemosys_value(
        db: Session,
        *,
        scenario_id: int,
        value_id: int,
        current_user: User,
        payload: dict,
    ) -> dict:
        """Actualiza una fila OSeMOSYS de escenario."""
        scenario = ScenarioService._require_manage_values(
            db, scenario_id=scenario_id, current_user=current_user
        )
        obj = db.get(OsemosysParamValue, value_id)
        if obj is None or int(obj.id_scenario) != scenario_id:
            raise NotFoundError("Valor OSeMOSYS no encontrado en el escenario.")
        previous_param_name = obj.param_name
        obj.param_name = ScenarioService._ensure_parameter_exists(
            db, param_name=str(payload.get("param_name") or "")
        )
        obj.id_region = ScenarioService._resolve_or_create_catalog_name(
            db, model=Region, name=payload.get("region_name"), label="Región"
        )
        obj.id_technology = ScenarioService._resolve_or_create_catalog_name(
            db, model=Technology, name=payload.get("technology_name"), label="Tecnología"
        )
        obj.id_fuel = ScenarioService._resolve_or_create_catalog_name(
            db, model=Fuel, name=payload.get("fuel_name"), label="Combustible"
        )
        obj.id_emission = ScenarioService._resolve_or_create_catalog_name(
            db, model=Emission, name=payload.get("emission_name"), label="Emisión"
        )
        ScenarioService._ensure_solver_if_provided(db, solver_name=payload.get("solver_name"))
        udc_code = (payload.get("udc_name") or "").strip() or None
        if udc_code:
            obj_udc = db.execute(select(UdcSet).where(UdcSet.code == udc_code)).scalar_one_or_none()
            if obj_udc is None:
                raise NotFoundError(f"UDC no encontrado: {udc_code}")
            obj.id_udc_set = int(obj_udc.id)
        else:
            obj.id_udc_set = None
        obj.year = payload.get("year")
        obj.value = float(payload.get("value"))
        ScenarioService._track_changed_params(
            scenario,
            param_names=[previous_param_name, obj.param_name],
        )
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("No se pudo actualizar el valor OSeMOSYS (posible duplicado de dimensiones).") from e
        db.refresh(obj)
        return ScenarioService._osemosys_value_to_public(db, value_id=int(obj.id))

    @staticmethod
    def deactivate_osemosys_value(
        db: Session,
        *,
        scenario_id: int,
        value_id: int,
        current_user: User,
    ) -> None:
        """Desactiva un valor OSeMOSYS eliminándolo del escenario."""
        scenario = ScenarioService._require_manage_values(
            db, scenario_id=scenario_id, current_user=current_user
        )
        obj = db.get(OsemosysParamValue, value_id)
        if obj is None or int(obj.id_scenario) != scenario_id:
            raise NotFoundError("Valor OSeMOSYS no encontrado en el escenario.")
        ScenarioService._track_changed_params(scenario, param_names=[obj.param_name])
        db.delete(obj)
        db.commit()


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Gobernar ciclo de vida de escenarios y su modelo de permisos.
#
# Posibles mejoras:
# - Reemplazar clonación fila-a-fila por inserción bulk para plantillas grandes.
# - Introducir roles explícitos (OWNER, EDITOR, REVIEWER) para legibilidad.
#
# Riesgos en producción:
# - Clonado transaccional de plantillas grandes puede elevar tiempos de respuesta.
# - Permiso `can_edit_direct` como proxy de administración puede ser ambiguo.
#
# Escalabilidad:
# - Principal costo en I/O de BD y tamaño del dataset clonado.
