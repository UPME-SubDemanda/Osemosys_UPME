"""Catálogo global de etiquetas de escenario."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models import ScenarioTag


class ScenarioTagService:
    @staticmethod
    def list_all(db: Session) -> list[ScenarioTag]:
        stmt = select(ScenarioTag).order_by(ScenarioTag.sort_order.asc(), ScenarioTag.name.asc())
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_by_id(db: Session, *, tag_id: int) -> ScenarioTag | None:
        return db.get(ScenarioTag, tag_id)

    @staticmethod
    def create(db: Session, *, name: str, color: str, sort_order: int) -> ScenarioTag:
        obj = ScenarioTag(name=name.strip(), color=color, sort_order=int(sort_order))
        db.add(obj)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("No se pudo crear la etiqueta (¿nombre duplicado?).") from e
        db.refresh(obj)
        return obj

    @staticmethod
    def update(
        db: Session,
        *,
        tag_id: int,
        name: str | None,
        color: str | None,
        sort_order: int | None,
    ) -> ScenarioTag:
        obj = db.get(ScenarioTag, tag_id)
        if obj is None:
            raise NotFoundError("Etiqueta no encontrada.")
        if name is not None:
            obj.name = name.strip()
        if color is not None:
            obj.color = color
        if sort_order is not None:
            obj.sort_order = int(sort_order)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("No se pudo actualizar la etiqueta (¿nombre duplicado?).") from e
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
