"""add justification to catalog change log

Revision ID: 20260219_0012
Revises: 20260219_0011
Create Date: 2026-02-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260219_0012"
down_revision = "20260219_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "catalog_change_log",
        sa.Column("justification", sa.Text(), nullable=True),
        schema="osemosys",
    )


def downgrade() -> None:
    op.drop_column("catalog_change_log", "justification", schema="osemosys")

