"""Repositorio para entidad `ParameterValue` (valores por defecto globales)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import ParameterValue


class ParameterValueRepository:
    """Acceso de lectura/escritura para valores por defecto."""

    @staticmethod
    def get_by_id(db: Session, parameter_value_id: int) -> ParameterValue | None:
        """Obtiene un `ParameterValue` por id."""
        return db.get(ParameterValue, parameter_value_id)

    @staticmethod
    def list_all(db: Session) -> list[ParameterValue]:
        """Lista todos los valores por defecto ordenados por id."""
        return list(
            db.query(ParameterValue)
            .order_by(ParameterValue.id.asc())
            .all()
        )

    @staticmethod
    def create(db: Session, payload: dict) -> ParameterValue:
        """Crea entidad a partir de payload validado por capa superior."""
        obj = ParameterValue(**payload)
        db.add(obj)
        return obj
