"""Catálogo de etiquetas de escenario agrupadas por categoría."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ConflictError, NotFoundError
from app.models import ScenarioTag, ScenarioTagCategory


class ScenarioTagService:
    @staticmethod
    def list_all(
        db: Session, *, category_id: int | None = None
    ) -> list[ScenarioTag]:
        stmt = (
            select(ScenarioTag)
            .options(joinedload(ScenarioTag.category))
            .join(ScenarioTag.category)
            .order_by(
                ScenarioTagCategory.hierarchy_level.asc(),
                ScenarioTagCategory.sort_order.asc(),
                ScenarioTag.sort_order.asc(),
                ScenarioTag.name.asc(),
            )
        )
        if category_id is not None:
            stmt = stmt.where(ScenarioTag.category_id == category_id)
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_by_id(db: Session, *, tag_id: int) -> ScenarioTag | None:
        stmt = (
            select(ScenarioTag)
            .options(joinedload(ScenarioTag.category))
            .where(ScenarioTag.id == tag_id)
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def create(
        db: Session,
        *,
        category_id: int,
        name: str,
        color: str,
        sort_order: int,
        is_exclusive_combination: bool | None = None,
    ) -> ScenarioTag:
        category = db.get(ScenarioTagCategory, category_id)
        if category is None:
            raise NotFoundError("Categoría no encontrada.")
        # Si no se envía explícitamente, heredar el flag de la categoría
        effective_exclusive = (
            bool(category.is_exclusive_combination)
            if is_exclusive_combination is None
            else bool(is_exclusive_combination)
        )
        obj = ScenarioTag(
            category_id=int(category_id),
            name=name.strip(),
            color=color,
            sort_order=int(sort_order),
            is_exclusive_combination=effective_exclusive,
        )
        db.add(obj)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError(
                "No se pudo crear la etiqueta (¿nombre duplicado en la categoría?)."
            ) from e
        db.refresh(obj)
        return obj

    @staticmethod
    def update(
        db: Session,
        *,
        tag_id: int,
        category_id: int | None,
        name: str | None,
        color: str | None,
        sort_order: int | None,
        is_exclusive_combination: bool | None = None,
    ) -> ScenarioTag:
        obj = db.get(ScenarioTag, tag_id)
        if obj is None:
            raise NotFoundError("Etiqueta no encontrada.")
        if category_id is not None:
            if db.get(ScenarioTagCategory, category_id) is None:
                raise NotFoundError("Categoría no encontrada.")
            obj.category_id = int(category_id)
        if name is not None:
            obj.name = name.strip()
        if color is not None:
            obj.color = color
        if sort_order is not None:
            obj.sort_order = int(sort_order)
        if is_exclusive_combination is not None:
            obj.is_exclusive_combination = bool(is_exclusive_combination)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("No se pudo actualizar la etiqueta.") from e
        db.refresh(obj)
        return obj

    @staticmethod
    def delete(db: Session, *, tag_id: int) -> None:
        obj = db.get(ScenarioTag, tag_id)
        if obj is None:
            raise NotFoundError("Etiqueta no encontrada.")
        db.delete(obj)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("No se pudo eliminar la etiqueta.") from e
