"""add scenario lineage support

Revision ID: 20260306_0020
Revises: 20260302_0019
Create Date: 2026-03-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260306_0020"
down_revision = "20260302_0019"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.add_column(
        "scenario",
        sa.Column("base_scenario_id", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_scenario_base_scenario_id",
        "scenario",
        ["base_scenario_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_scenario_base_scenario_id_scenario",
        "scenario",
        "scenario",
        ["base_scenario_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_scenario_base_scenario_id_scenario",
        "scenario",
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_index(
        "ix_scenario_base_scenario_id",
        table_name="scenario",
        schema=SCHEMA,
    )
    op.drop_column("scenario", "base_scenario_id", schema=SCHEMA)
