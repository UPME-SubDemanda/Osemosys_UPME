"""add composite index (id_scenario, param_name) on osemosys_param_value

Revision ID: 20260225_0015
Revises: 20260219_0014
Create Date: 2026-02-25
"""

from __future__ import annotations

from alembic import op

revision = "20260225_0015"
down_revision = "20260219_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_opv_scenario_param",
        "osemosys_param_value",
        ["id_scenario", "param_name"],
        schema="osemosys",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_opv_scenario_param",
        table_name="osemosys_param_value",
        schema="osemosys",
    )
