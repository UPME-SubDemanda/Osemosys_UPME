"""Asignación de etiquetas a escenarios con detección de conflictos.

Reglas de conflicto:
1. `max_tags_per_scenario=1` en la categoría → al asignar, se quita cualquier
   otra etiqueta de la misma categoría en ese escenario (conflicto interno, se
   auto-resuelve sin confirmación del usuario).
2. `is_exclusive_combination=True` en la categoría → la combinación de
   (tag de esta categoría + tags de otras categorías ya presentes en el
   escenario) debe ser única entre escenarios. Si otro escenario ya tiene la
   misma combinación, se reporta conflicto (requiere `force=True` para
   confirmar quitar la etiqueta del otro escenario).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ConflictError, NotFoundError
from app.models import (
    Scenario,
    ScenarioTag,
    ScenarioTagCategory,
    ScenarioTagLink,
)


class TagAssignmentConflict(Exception):
    """Se lanza cuando hay un conflicto que requiere confirmación del usuario."""

    def __init__(self, detail: dict):
        super().__init__(detail.get("reason", "conflict"))
        self.detail = detail


class ScenarioTagAssignmentService:
    @staticmethod
    def _get_tag(db: Session, tag_id: int) -> ScenarioTag:
        tag = (
            db.execute(
                select(ScenarioTag)
                .options(joinedload(ScenarioTag.category))
                .where(ScenarioTag.id == tag_id)
            ).scalar_one_or_none()
        )
        if tag is None:
            raise NotFoundError("Etiqueta no encontrada.")
        return tag

    @staticmethod
    def _current_tag_ids(db: Session, scenario_id: int) -> list[int]:
        rows = (
            db.execute(
                select(ScenarioTagLink.tag_id).where(
                    ScenarioTagLink.scenario_id == scenario_id
                )
            )
            .scalars()
            .all()
        )
        return [int(r) for r in rows]

    @staticmethod
    def _signature(
        db: Session,
        *,
        scenario_id: int,
        exclude_category_id: int,
        extra_tag_id: int | None = None,
    ) -> frozenset[int]:
        """Firma combinatoria del escenario para exclusividad.

        = conjunto de tag_ids del escenario cuyas categorías son DIFERENTES a
        `exclude_category_id`. Si se pasa `extra_tag_id` (simulando una
        asignación pendiente), se añade solo si su categoría también es
        distinta a la excluida.
        """
        current_ids = ScenarioTagAssignmentService._current_tag_ids(db, scenario_id)
        sig: set[int] = set()
        if current_ids:
            rows = (
                db.execute(
                    select(ScenarioTag.id, ScenarioTag.category_id).where(
                        ScenarioTag.id.in_(current_ids)
                    )
                )
                .all()
            )
            for tid, cid in rows:
                if int(cid) != int(exclude_category_id):
                    sig.add(int(tid))
        if extra_tag_id is not None:
            extra = db.get(ScenarioTag, int(extra_tag_id))
            if extra is not None and int(extra.category_id) != int(exclude_category_id):
                sig.add(int(extra.id))
        return frozenset(sig)

    @staticmethod
    def _find_exclusive_conflict(
        db: Session,
        *,
        scenario_id: int,
        target_tag: ScenarioTag,
        extra_tag_id: int | None = None,
    ) -> dict | None:
        """Busca otro escenario con `target_tag` cuya firma sea idéntica.

        La firma de un escenario = tags en categorías distintas a la de
        `target_tag`. Dos escenarios no pueden compartir `target_tag` con la
        misma firma. El conjunto vacío {} cuenta como firma válida: si dos
        escenarios tienen `target_tag` y ambos tienen firma vacía (sin tags
        en otras categorías), también se considera colisión.

        `extra_tag_id` simula una asignación pendiente en el escenario actual
        (útil para la validación inversa cuando se añade un tag secundario
        que completa la combinación de un tag exclusivo ya presente).
        """
        current_sig = ScenarioTagAssignmentService._signature(
            db,
            scenario_id=scenario_id,
            exclude_category_id=int(target_tag.category_id),
            extra_tag_id=extra_tag_id,
        )

        other_scenarios = (
            db.execute(
                select(Scenario)
                .join(
                    ScenarioTagLink, ScenarioTagLink.scenario_id == Scenario.id
                )
                .where(
                    ScenarioTagLink.tag_id == target_tag.id,
                    Scenario.id != scenario_id,
                )
            )
            .scalars()
            .unique()
            .all()
        )
        for other in other_scenarios:
            other_sig = ScenarioTagAssignmentService._signature(
                db,
                scenario_id=int(other.id),
                exclude_category_id=int(target_tag.category_id),
            )
            if current_sig == other_sig:
                return {
                    "scenario_id": int(other.id),
                    "scenario_name": other.name,
                    "conflicting_tag_id": int(target_tag.id),
                    "conflicting_tag_name": target_tag.name,
                    "reason": "exclusive_combination",
                }
        return None

    @staticmethod
    def assign(
        db: Session,
        *,
        scenario_id: int,
        tag_id: int,
        force: bool = False,
    ) -> list[ScenarioTag]:
        """Asigna una etiqueta al escenario aplicando reglas de unicidad.

        Retorna la lista completa de tags del escenario tras la operación.
        Si hay un conflicto exclusivo no resuelto, lanza TagAssignmentConflict.
        """
        scenario = db.get(Scenario, scenario_id)
        if scenario is None:
            raise NotFoundError("Escenario no encontrado.")
        tag = ScenarioTagAssignmentService._get_tag(db, tag_id)

        # Regla 1: max_tags_per_scenario=1 → reemplaza la etiqueta previa de la misma categoría
        if tag.category.max_tags_per_scenario == 1:
            same_cat_links = (
                db.execute(
                    select(ScenarioTagLink)
                    .join(ScenarioTag, ScenarioTag.id == ScenarioTagLink.tag_id)
                    .where(
                        ScenarioTagLink.scenario_id == scenario_id,
                        ScenarioTag.category_id == tag.category_id,
                        ScenarioTag.id != tag.id,
                    )
                )
                .scalars()
                .all()
            )
            for link in same_cat_links:
                db.delete(link)

        # Regla 2: exclusividad combinatoria con otros escenarios
        if tag.is_exclusive_combination:
            conflict = ScenarioTagAssignmentService._find_exclusive_conflict(
                db, scenario_id=scenario_id, target_tag=tag
            )
            if conflict is not None:
                if not force:
                    db.rollback()
                    raise TagAssignmentConflict(conflict)
                # Al forzar: quitar el tag en conflicto del otro escenario
                db.execute(
                    ScenarioTagLink.__table__.delete().where(
                        ScenarioTagLink.scenario_id == conflict["scenario_id"],
                        ScenarioTagLink.tag_id == conflict["conflicting_tag_id"],
                    )
                )

        # Exclusividad inversa: añadir un tag no-exclusivo puede cerrar una
        # combinación exclusiva que otro escenario ya tiene. Re-evaluamos cada
        # tag exclusivo del escenario actual simulando que el nuevo tag ya
        # está presente.
        if not tag.is_exclusive_combination:
            current_ids = ScenarioTagAssignmentService._current_tag_ids(
                db, scenario_id
            )
            if current_ids:
                exclusive_tags = (
                    db.execute(
                        select(ScenarioTag)
                        .options(joinedload(ScenarioTag.category))
                        .where(ScenarioTag.id.in_(current_ids))
                    )
                    .scalars()
                    .all()
                )
                for et in exclusive_tags:
                    if not et.is_exclusive_combination:
                        continue
                    conflict = ScenarioTagAssignmentService._find_exclusive_conflict(
                        db,
                        scenario_id=scenario_id,
                        target_tag=et,
                        extra_tag_id=int(tag.id),
                    )
                    if conflict is None:
                        continue
                    if not force:
                        db.rollback()
                        raise TagAssignmentConflict(conflict)
                    db.execute(
                        ScenarioTagLink.__table__.delete().where(
                            ScenarioTagLink.scenario_id == conflict["scenario_id"],
                            ScenarioTagLink.tag_id == conflict["conflicting_tag_id"],
                        )
                    )

        # Insertar el link si no existe
        existing = db.get(ScenarioTagLink, (scenario_id, tag.id))
        if existing is None:
            db.add(ScenarioTagLink(scenario_id=scenario_id, tag_id=tag.id))

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise ConflictError(f"No se pudo asignar la etiqueta: {e}") from e

        return ScenarioTagAssignmentService.list_tags(db, scenario_id=scenario_id)

    @staticmethod
    def remove(db: Session, *, scenario_id: int, tag_id: int) -> list[ScenarioTag]:
        scenario = db.get(Scenario, scenario_id)
        if scenario is None:
            raise NotFoundError("Escenario no encontrado.")
        link = db.get(ScenarioTagLink, (scenario_id, tag_id))
        if link is not None:
            db.delete(link)
            db.commit()
        return ScenarioTagAssignmentService.list_tags(db, scenario_id=scenario_id)

    @staticmethod
    def list_tags(db: Session, *, scenario_id: int) -> list[ScenarioTag]:
        stmt = (
            select(ScenarioTag)
            .options(joinedload(ScenarioTag.category))
            .join(ScenarioTagLink, ScenarioTagLink.tag_id == ScenarioTag.id)
            .join(ScenarioTagCategory, ScenarioTagCategory.id == ScenarioTag.category_id)
            .where(ScenarioTagLink.scenario_id == scenario_id)
            .order_by(
                ScenarioTagCategory.hierarchy_level.asc(),
                ScenarioTagCategory.sort_order.asc(),
                ScenarioTag.sort_order.asc(),
                ScenarioTag.name.asc(),
            )
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def replace_tags(
        db: Session,
        *,
        scenario_id: int,
        tag_ids: list[int],
    ) -> list[ScenarioTag]:
        """Reemplaza el conjunto de tags del escenario por `tag_ids` (sin conflictos
        entre escenarios — solo valida existencia). Respeta `max_tags_per_scenario`:
        si hay varios tags de la misma categoría con max=1, conserva solo el último.
        """
        scenario = db.get(Scenario, scenario_id)
        if scenario is None:
            raise NotFoundError("Escenario no encontrado.")
        # Quita todos
        db.execute(
            ScenarioTagLink.__table__.delete().where(
                ScenarioTagLink.scenario_id == scenario_id
            )
        )
        if not tag_ids:
            db.commit()
            return []
        # Valida que todos existen
        tags = (
            db.execute(
                select(ScenarioTag)
                .options(joinedload(ScenarioTag.category))
                .where(ScenarioTag.id.in_(list(set(int(t) for t in tag_ids))))
            )
            .scalars()
            .all()
        )
        if len(tags) != len(set(tag_ids)):
            raise NotFoundError("Al menos una etiqueta no existe.")
        # Aplica regla de max=1 por categoría (último gana)
        by_cat: dict[int, int] = {}
        for tid in tag_ids:
            t = next((x for x in tags if x.id == int(tid)), None)
            if t is None:
                continue
            if t.category.max_tags_per_scenario == 1:
                by_cat[t.category_id] = int(tid)
            else:
                by_cat.setdefault(-int(tid), int(tid))  # preserva otros sin conflicto
        final_ids = list({v for v in by_cat.values()})
        for tid in final_ids:
            db.add(ScenarioTagLink(scenario_id=scenario_id, tag_id=tid))
        db.commit()
        return ScenarioTagAssignmentService.list_tags(db, scenario_id=scenario_id)
