"""saved_chart_template.report_title — título personalizado al renderizar en reportes.

Revision ID: 20260424_0002
Revises: 20260424_0001
Create Date: 2026-04-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260424_0002"
down_revision = "20260424_0001"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.add_column(
        "saved_chart_template",
        sa.Column("report_title", sa.String(length=255), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("saved_chart_template", "report_title", schema=SCHEMA)
