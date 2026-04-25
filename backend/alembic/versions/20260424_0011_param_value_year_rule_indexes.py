"""add partial index for OSeMOSYS wide year-rule filters (nonzero values)

`ix_osemosys_param_value_scenario_year` on (id_scenario, year) is created in
``20260424_0009``; this migration only adds the partial index used for
``value <> 0``-style rules.

Revision ID: 20260424_0011
Revises: 20260424_0010
Create Date: 2026-04-24
"""

from __future__ import annotations

from alembic import op

revision = "20260424_0011"
down_revision = "20260424_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_opv_scenario_year_nonzero_param
            ON osemosys.osemosys_param_value (id_scenario, year, param_name)
            WHERE value <> 0
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            """
            DROP INDEX CONCURRENTLY IF EXISTS osemosys.ix_opv_scenario_year_nonzero_param
            """
        )
