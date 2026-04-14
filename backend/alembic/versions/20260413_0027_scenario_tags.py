"""scenario_tag and scenario.tag_id

Revision ID: 20260413_0027
Revises: 20260331_0026
Create Date: 2026-04-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260413_0027"
down_revision = "20260331_0026"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.create_table(
        "scenario_tag",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_scenario_tag_name"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_scenario_tag_sort_order",
        "scenario_tag",
        ["sort_order"],
        unique=False,
        schema=SCHEMA,
    )
    op.add_column(
        "scenario",
        sa.Column("tag_id", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index("ix_scenario_tag_id", "scenario", ["tag_id"], unique=False, schema=SCHEMA)
    op.create_foreign_key(
        "fk_scenario_tag_id_scenario_tag",
        "scenario",
        "scenario_tag",
        ["tag_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_scenario_tag_id_scenario_tag", "scenario", schema=SCHEMA, type_="foreignkey")
    op.drop_index("ix_scenario_tag_id", table_name="scenario", schema=SCHEMA)
    op.drop_column("scenario", "tag_id", schema=SCHEMA)
    op.drop_index("ix_scenario_tag_sort_order", table_name="scenario_tag", schema=SCHEMA)
    op.drop_table("scenario_tag", schema=SCHEMA)
