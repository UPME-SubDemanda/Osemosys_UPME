"""simulation_job.display_name — nombre opcional de la corrida

Revision ID: 20260415_0028
Revises: 20260413_0027
Create Date: 2026-04-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260415_0028"
down_revision = "20260413_0027"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.add_column(
        "simulation_job",
        sa.Column("display_name", sa.String(length=255), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("simulation_job", "display_name", schema=SCHEMA)
