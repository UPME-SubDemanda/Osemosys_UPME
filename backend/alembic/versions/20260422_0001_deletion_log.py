"""deletion_log — bitácora de eliminaciones de escenarios y simulaciones

Revision ID: 20260422_0001
Revises: 20260421_0034
Create Date: 2026-04-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260422_0001"
down_revision = "20260421_0034"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.create_table(
        "deletion_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("entity_name", sa.String(length=400), nullable=False),
        sa.Column(
            "deleted_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core.user.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("deleted_by_username", sa.String(length=100), nullable=False),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "details_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.CheckConstraint(
            "entity_type IN ('SCENARIO','SIMULATION_JOB')",
            name="deletion_log_entity_type",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_deletion_log_deleted_at",
        "deletion_log",
        [sa.text("deleted_at DESC")],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_deletion_log_entity",
        "deletion_log",
        ["entity_type", "entity_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_deletion_log_entity", table_name="deletion_log", schema=SCHEMA)
    op.drop_index("ix_deletion_log_deleted_at", table_name="deletion_log", schema=SCHEMA)
    op.drop_table("deletion_log", schema=SCHEMA)
