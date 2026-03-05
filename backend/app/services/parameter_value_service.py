"""Servicio de negocio para valores por defecto de parámetros.

parameter_value ya no está ligado a escenarios; es un almacén global de defaults.
La autorización se basa en permisos del usuario (import manager o admin).
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models import ParameterValueAudit, Solver
from app.repositories.parameter_value_repository import ParameterValueRepository


class ParameterValueService:
    """Reglas de negocio para `ParameterValue` (defaults globales)."""

    @staticmethod
    def list_all(db: Session):
        """Lista todos los valores por defecto."""
        return ParameterValueRepository.list_all(db)

    @staticmethod
    def create(db: Session, *, payload: dict):
        """Crea nuevo `ParameterValue` global."""
        if not payload.get("id_solver"):
            default_solver = db.query(Solver).filter(Solver.name == "default").first()
            if default_solver is None:
                default_solver = Solver(name="default", is_active=True)
                db.add(default_solver)
                db.flush()
            payload["id_solver"] = default_solver.id

        obj = ParameterValueRepository.create(db, payload)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError(
                "No se pudo crear el parameter_value (revisar llaves foráneas/constraints)."
            ) from e
        db.refresh(obj)
        return obj

    @staticmethod
    def update(
        db: Session,
        *,
        parameter_value_id: int,
        value: float,
        unit: str | None,
        changed_by: str,
    ):
        """Actualiza valor/unidad y registra auditoría."""
        parameter_value = ParameterValueRepository.get_by_id(db, parameter_value_id)
        if not parameter_value:
            raise NotFoundError("ParameterValue no encontrado.")

        old_value = parameter_value.value
        parameter_value.value = value
        parameter_value.unit = unit

        db.add(
            ParameterValueAudit(
                id_parameter_value=parameter_value.id,
                old_value=old_value,
                new_value=value,
                changed_by=changed_by,
            )
        )

        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise ConflictError("No se pudo actualizar el parameter_value.") from e
        db.refresh(parameter_value)
        return parameter_value
