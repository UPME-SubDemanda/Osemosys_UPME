"""saved_chart_template.synthetic_series — series manuales overlay.

Revision ID: 20260424_0006
Revises: 20260424_0005
Create Date: 2026-04-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260424_0006"
down_revision = "20260424_0005"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.add_column(
        "saved_chart_template",
        sa.Column("synthetic_series", postgresql.JSONB(), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("saved_chart_template", "synthetic_series", schema=SCHEMA)
