"""CRUD de categorías jerárquicas de etiquetas de escenario."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models import ScenarioTagCategory


class ScenarioTagCategoryService:
    @staticmethod
    def list_all(db: Session) -> list[ScenarioTagCategory]:
        stmt = select(ScenarioTagCategory).order_by(
            ScenarioTagCategory.hierarchy_level.asc(),
            ScenarioTagCategory.sort_order.asc(),
            ScenarioTagCategory.name.asc(),
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def create(
        db: Session,
        *,
        name: str,
        hierarchy_level: int,
        sort_order: int,
        max_tags_per_scenario: int | None,
        is_exclusive_combination: bool,
        default_color: str,
    ) -> ScenarioTagCategory:
        obj = ScenarioTagCategory(
            name=name.strip(),
            hierarchy_level=int(hierarchy_level),
            sort_order=int(sort_order),
            max_tags_per_scenario=max_tags_per_scenario,
            is_exclusive_combination=bool(is_exclusive_combination),
            default_color=default_color,
        )
        db.add(obj)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("No se pudo crear la categoría (¿nombre duplicado?).") from e
        db.refresh(obj)
        return obj

    @staticmethod
    def update(
        db: Session,
        *,
        category_id: int,
        name: str | None,
        hierarchy_level: int | None,
        sort_order: int | None,
        max_tags_per_scenario: int | None,
        is_exclusive_combination: bool | None,
        default_color: str | None,
        max_tags_explicit: bool = False,
    ) -> ScenarioTagCategory:
        obj = db.get(ScenarioTagCategory, category_id)
        if obj is None:
            raise NotFoundError("Categoría no encontrada.")
        if name is not None:
            obj.name = name.strip()
        if hierarchy_level is not None:
            obj.hierarchy_level = int(hierarchy_level)
        if sort_order is not None:
            obj.sort_order = int(sort_order)
        if max_tags_explicit:
            obj.max_tags_per_scenario = max_tags_per_scenario
        if is_exclusive_combination is not None:
            obj.is_exclusive_combination = bool(is_exclusive_combination)
        if default_color is not None:
            obj.default_color = default_color
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("No se pudo actualizar la categoría.") from e
        db.refresh(obj)
        return obj

    @staticmethod
    def delete(db: Session, *, category_id: int) -> None:
        obj = db.get(ScenarioTagCategory, category_id)
        if obj is None:
            raise NotFoundError("Categoría no encontrada.")
        db.delete(obj)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError(
                "No se pudo eliminar la categoría; elimina primero sus etiquetas."
            ) from e
