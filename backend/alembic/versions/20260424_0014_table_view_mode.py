"""saved_chart_template.table_period_years / table_cumulative — view_mode='table'.

Revision ID: 20260424_0014
Revises: 20260424_0013
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260424_0014"
down_revision = "20260424_0013"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.add_column(
        "saved_chart_template",
        sa.Column("table_period_years", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "saved_chart_template",
        sa.Column("table_cumulative", sa.Boolean(), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("saved_chart_template", "table_cumulative", schema=SCHEMA)
    op.drop_column("saved_chart_template", "table_period_years", schema=SCHEMA)
