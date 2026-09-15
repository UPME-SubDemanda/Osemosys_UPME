"""Fix wrong color_fn_key for H2, gas, bioenergía, electrolisis charts.

All _make_color_fn_fija closures shared __name__="_fn", causing
COLOR_FN_NAME_TO_KEY to map all of them to "liquidos_import".

Revision ID: 20260914_0050
Revises: 20260914_0049
Create Date: 2026-09-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260914_0050"
down_revision = "20260914_0049"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"

CORRECTIONS = {
    "cap_h2": "h2_produccion",
    "h2_consumo": "h2_consumo",
    "cap_electrolisis_verde": "electrolisis",
    "gas_produccion": "gas_produccion",
    "gas_capacidad": "gas_produccion",
    "gas_import_export": "gas_produccion",
    "oferta_bioenergia": "bioenergia",
}


def upgrade() -> None:
    conn = op.get_bind()
    total = 0
    for tipo, correct_key in CORRECTIONS.items():
        result = conn.execute(
            sa.text(
                f"""
                UPDATE {SCHEMA}.catalog_meta_chart_config
                SET color_fn_key = :correct_key,
                    updated_at = now()
                WHERE tipo = :tipo
                  AND color_fn_key != :correct_key
                """
            ),
            {"tipo": tipo, "correct_key": correct_key},
        )
        if result.rowcount > 0:
            print(f"  {tipo}: liquidos_import → {correct_key} (filas={result.rowcount})")
            total += result.rowcount
        else:
            print(f"  {tipo}: ya correcto ({correct_key})")
    print(f"Total filas actualizadas: {total}")


def downgrade() -> None:
    conn = op.get_bind()
    for tipo in CORRECTIONS:
        conn.execute(
            sa.text(
                f"""
                UPDATE {SCHEMA}.catalog_meta_chart_config
                SET color_fn_key = 'liquidos_import',
                    updated_at = now()
                WHERE tipo = :tipo
                """
            ),
            {"tipo": tipo},
        )
