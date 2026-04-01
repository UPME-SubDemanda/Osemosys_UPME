"""Registro y consulta de auditoría sobre `osemosys_param_value`."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import OsemosysParamValueAudit


def user_actor(current_user) -> str:
    """Nombre de usuario para `changed_by` (solo API; Excel u otros usan prefijo `system:`)."""
    return str(current_user.username)


class OsemosysParamAuditService:
    @staticmethod
    def append(
        db: Session,
        *,
        scenario_id: int,
        param_name: str,
        id_osemosys_param_value: int | None,
        action: str,
        old_value: float | None,
        new_value: float | None,
        dimensions_json: dict | None,
        source: str,
        changed_by: str,
    ) -> None:
        db.add(
            OsemosysParamValueAudit(
                id_scenario=scenario_id,
                param_name=param_name,
                id_osemosys_param_value=id_osemosys_param_value,
                action=action,
                old_value=old_value,
                new_value=new_value,
                dimensions_json=dimensions_json,
                source=source,
                changed_by=changed_by,
            )
        )

    @staticmethod
    def list_for_param(
        db: Session,
        *,
        scenario_id: int,
        param_name: str,
        offset: int,
        limit: int,
    ) -> tuple[list[OsemosysParamValueAudit], int]:
        where = (
            (OsemosysParamValueAudit.id_scenario == scenario_id)
            & (OsemosysParamValueAudit.param_name == param_name)
        )
        total = int(
            db.scalar(select(func.count()).select_from(OsemosysParamValueAudit).where(where)) or 0
        )
        stmt = (
            select(OsemosysParamValueAudit)
            .where(where)
            .order_by(OsemosysParamValueAudit.created_at.desc(), OsemosysParamValueAudit.id.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = list(db.execute(stmt).scalars().all())
        return rows, total
