"""Índice compuesto (id_scenario, year) para acelerar year_rules y queries por año.

La subquery `SELECT id FROM osemosys_param_value WHERE id_scenario=:s AND year=:y`
usaba `ix_osemosys_param_value_year` (solo año), escaneando filas de TODOS los
escenarios para luego filtrar por scenario en memoria. Con (scenario, year)
el planner va directo al subconjunto relevante. Mejora ~25× en escenarios
con muchos parámetros.

Revision ID: 20260424_0009
Revises: 20260424_0008
Create Date: 2026-04-24
"""

from __future__ import annotations

from alembic import op

revision = "20260424_0009"
down_revision = "20260424_0008"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"
TABLE = "osemosys_param_value"
INDEX = "ix_osemosys_param_value_scenario_year"


def upgrade() -> None:
    op.create_index(
        INDEX,
        TABLE,
        ["id_scenario", "year"],
        schema=SCHEMA,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(INDEX, table_name=TABLE, schema=SCHEMA, if_exists=True)
