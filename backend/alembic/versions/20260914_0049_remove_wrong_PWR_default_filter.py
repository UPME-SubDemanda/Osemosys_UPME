"""Remove wrong TECNOLOGIAS_PWR default filter from emisiones_total, emisiones_sectorial, exp_liquidos_gas.

Revision ID: 20260914_0049
Revises: 20260914_0048
Create Date: 2026-09-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260914_0049"
down_revision = "20260914_0048"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"
AFFECTED_TYPES = ("emisiones_total", "emisiones_sectorial", "exp_liquidos_gas")


def upgrade() -> None:
    conn = op.get_bind()
    for tipo in AFFECTED_TYPES:
        result = conn.execute(
            sa.text(
                f"""
                UPDATE {SCHEMA}.catalog_meta_chart_config
                SET filtro_params_json = NULL,
                    filtro_group_id = NULL,
                    updated_at = now()
                WHERE tipo = :tipo
                  AND (filtro_params_json->>'group') IS NOT NULL
                  AND filtro_params_json->>'_filter_fn' IS NULL
                """
            ),
            {"tipo": tipo},
        )
        if result.rowcount > 0:
            print(f"  {tipo}: limpiado filtro_params_json (filas={result.rowcount})")
        else:
            print(f"  {tipo}: sin cambios (ya correcto o no encontrado)")


def downgrade() -> None:
    conn = op.get_bind()
    for tipo in AFFECTED_TYPES:
        conn.execute(
            sa.text(
                f"""
                UPDATE {SCHEMA}.catalog_meta_chart_config
                SET filtro_params_json = '{"group": "TECNOLOGIAS_PWR"}'::jsonb,
                    updated_at = now()
                WHERE tipo = :tipo
                  AND filtro_params_json IS NULL
                """
            ),
            {"tipo": tipo},
        )
