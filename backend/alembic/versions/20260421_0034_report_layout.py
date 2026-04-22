"""report_template.layout (árbol de categorías override manual)

Revision ID: 20260421_0034
Revises: 20260421_0033
Create Date: 2026-04-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260421_0034"
down_revision = "20260421_0033"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.add_column(
        "report_template",
        sa.Column(
            "layout",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("report_template", "layout", schema=SCHEMA)
