"""core.user.is_admin — flag que autoriza eliminar contenido ajeno.

Revision ID: 20260423_0001
Revises: 20260422_0001
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260423_0001"
down_revision = "20260422_0001"
branch_labels = None
depends_on = None

SCHEMA = "core"


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("user", "is_admin", schema=SCHEMA)
