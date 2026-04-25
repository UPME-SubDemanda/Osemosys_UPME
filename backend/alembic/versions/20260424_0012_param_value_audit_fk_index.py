"""add index for OSeMOSYS value audit FK cleanup

Revision ID: 20260424_0012
Revises: 20260424_0011
Create Date: 2026-04-24
"""

from __future__ import annotations

from alembic import op

revision = "20260424_0012"
down_revision = "20260424_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_osemosys_param_audit_value_id
            ON osemosys.osemosys_param_value_audit (id_osemosys_param_value)
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            """
            DROP INDEX CONCURRENTLY IF EXISTS osemosys.ix_osemosys_param_audit_value_id
            """
        )
