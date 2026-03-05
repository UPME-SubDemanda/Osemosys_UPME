"""add can_import_official_data permission to core.user

Revision ID: 20260219_0010
Revises: 20260219_0009
Create Date: 2026-02-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260219_0010"
down_revision = "20260219_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("can_import_official_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema="core",
    )


def downgrade() -> None:
    op.drop_column("user", "can_import_official_data", schema="core")
