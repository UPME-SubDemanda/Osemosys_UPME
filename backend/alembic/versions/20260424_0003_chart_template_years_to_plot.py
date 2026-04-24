"""saved_chart_template.years_to_plot — años a graficar cuando compare_mode='by-year'.

Revision ID: 20260424_0003
Revises: 20260424_0002
Create Date: 2026-04-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260424_0003"
down_revision = "20260424_0002"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.add_column(
        "saved_chart_template",
        sa.Column("years_to_plot", postgresql.JSONB(), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("saved_chart_template", "years_to_plot", schema=SCHEMA)
