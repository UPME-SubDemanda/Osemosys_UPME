"""remove id_scenario from parameter_value — defaults store

parameter_value becomes a global defaults table (no scenario association).
Each new scenario copies these defaults into osemosys_param_value.

Revision ID: 20260227_0017
Revises: 20260227_0016
Create Date: 2026-02-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260227_0017"
down_revision = "20260227_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0. Clear child tables that hold FK refs to parameter_value rows
    #    (output_parameter_value is dead code; will be dropped in 0018).
    op.execute(sa.text("DELETE FROM osemosys.output_parameter_value"))
    op.execute(sa.text("DELETE FROM osemosys.parameter_storage"))
    op.execute(sa.text("DELETE FROM osemosys.parameter_value_audit"))

    # 1. Deduplicate: keep one row per unique dimension set (lowest id wins).
    op.execute(sa.text("""
        DELETE FROM osemosys.parameter_value
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM osemosys.parameter_value
            GROUP BY id_parameter, id_region, id_technology, id_fuel,
                     id_emission, id_solver, year
        )
    """))

    # 2. Drop indexes that reference id_scenario.
    op.drop_index("ix_parameter_value_id_scenario", table_name="parameter_value", schema="osemosys")
    op.drop_index("ix_parameter_value_scenario_parameter_year", table_name="parameter_value", schema="osemosys")

    # 3. Drop FK constraint, then the column.
    op.drop_constraint(
        "parameter_value_id_scenario_fkey",
        table_name="parameter_value",
        schema="osemosys",
        type_="foreignkey",
    )
    op.drop_column("parameter_value", "id_scenario", schema="osemosys")

    # 4. Add unique constraint on remaining dimensions.
    op.create_unique_constraint(
        "uq_parameter_value_dims",
        "parameter_value",
        ["id_parameter", "id_region", "id_technology", "id_fuel", "id_emission", "id_solver", "year"],
        schema="osemosys",
    )


def downgrade() -> None:
    op.drop_constraint("uq_parameter_value_dims", "parameter_value", schema="osemosys", type_="unique")

    op.add_column(
        "parameter_value",
        sa.Column("id_scenario", sa.Integer(), nullable=True),
        schema="osemosys",
    )
    op.create_foreign_key(
        "parameter_value_id_scenario_fkey",
        "parameter_value",
        "scenario",
        ["id_scenario"],
        ["id"],
        source_schema="osemosys",
        referent_schema="osemosys",
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_parameter_value_id_scenario",
        "parameter_value",
        ["id_scenario"],
        schema="osemosys",
    )
    op.create_index(
        "ix_parameter_value_scenario_parameter_year",
        "parameter_value",
        ["id_scenario", "id_parameter", "year"],
        schema="osemosys",
    )
