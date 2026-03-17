"""add changed param names to scenario lineage

Revision ID: 20260306_0021
Revises: 20260306_0020
Create Date: 2026-03-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260306_0021"
down_revision = "20260306_0020"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.add_column(
        "scenario",
        sa.Column("changed_param_names", sa.JSON(), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("scenario", "changed_param_names", schema=SCHEMA)
