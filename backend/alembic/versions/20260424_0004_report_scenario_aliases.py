"""report_template.scenario_aliases — alias persistentes por escenario global.

Revision ID: 20260424_0004
Revises: 20260424_0003
Create Date: 2026-04-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260424_0004"
down_revision = "20260424_0003"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.add_column(
        "report_template",
        sa.Column("scenario_aliases", JSONB(), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("report_template", "scenario_aliases", schema=SCHEMA)
