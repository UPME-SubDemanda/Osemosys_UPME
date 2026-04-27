"""report_template.year_from / year_to — rango de años persistido por reporte.

Revision ID: 20260424_0013
Revises: 20260424_0012
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260424_0013"
down_revision = "20260424_0012"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.add_column(
        "report_template",
        sa.Column("year_from", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "report_template",
        sa.Column("year_to", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("report_template", "year_to", schema=SCHEMA)
    op.drop_column("report_template", "year_from", schema=SCHEMA)
