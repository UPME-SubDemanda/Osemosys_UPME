"""Completa la entidad del filtro de emisiones GEI en el catálogo.

Revision ID: 20260902_0044
Revises: 20260606_0043
Create Date: 2026-09-02
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "20260902_0044"
down_revision = "20260606_0043"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"
CHART_TYPE = "emisiones_gei"
OLD_FILTER_PARAMS = {
    "group": "COMBUSTIBLES_GEI",
    "_filter_fn": "_filtro_gei",
}
NEW_FILTER_PARAMS = {
    "group": "COMBUSTIBLES_GEI",
    "entity": "FUEL",
    "_filter_fn": "_filtro_gei",
}


def _update_if_matches(expected: dict[str, str], replacement: dict[str, str]) -> int:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA}.catalog_meta_chart_config
            SET filtro_params_json = CAST(:replacement AS jsonb),
                updated_at = now()
            WHERE tipo = :chart_type
              AND filtro_params_json = CAST(:expected AS jsonb)
            """
        ),
        {
            "chart_type": CHART_TYPE,
            "expected": json.dumps(expected),
            "replacement": json.dumps(replacement),
        },
    )
    return result.rowcount


def upgrade() -> None:
    updated = _update_if_matches(OLD_FILTER_PARAMS, NEW_FILTER_PARAMS)
    if updated == 1:
        return
    # Instalación limpia o re-ejecución: la fila puede no existir aún (la siembra
    # el startup-sync del API desde chart_menu, ya en formato nuevo) o estar ya
    # actualizada. Solo falla si existe en un formato distinto al esperado.
    conn = op.get_bind()
    current = conn.execute(
        sa.text(
            f"SELECT filtro_params_json FROM {SCHEMA}.catalog_meta_chart_config "
            f"WHERE tipo = :chart_type"
        ),
        {"chart_type": CHART_TYPE},
    ).scalar_one_or_none()
    if current is None:
        return
    # psycopg decodifica JSONB a dict — comparación directa
    if current == NEW_FILTER_PARAMS:
        return
    raise RuntimeError(
        "Se esperaba actualizar exactamente una fila de "
        f"{SCHEMA}.catalog_meta_chart_config para tipo={CHART_TYPE!r}; "
        f"filas actualizadas: {updated} y el estado actual no coincide con "
        "ningún formato conocido."
    )


def downgrade() -> None:
    _update_if_matches(NEW_FILTER_PARAMS, OLD_FILTER_PARAMS)
