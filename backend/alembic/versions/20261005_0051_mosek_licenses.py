"""Add encrypted global and per-user MOSEK license storage.

Revision ID: 20261005_0051
Revises: 20260914_0050
Create Date: 2026-10-05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261005_0051"
down_revision = "20260914_0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "solver_license",
        sa.Column("scope_key", sa.String(length=48), primary_key=True),
        sa.Column("encrypted_content", sa.LargeBinary(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_by",
            sa.Uuid(),
            sa.ForeignKey("core.user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        schema="core",
    )


def downgrade() -> None:
    op.drop_table("solver_license", schema="core")
