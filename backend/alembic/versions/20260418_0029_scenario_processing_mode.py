"""add scenario processing mode for preprocessed csv imports

Revision ID: 20260418_0029
Revises: 20260417_0028
Create Date: 2026-04-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260418_0029"
down_revision = "20260417_0028"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.add_column(
        "scenario",
        sa.Column("processing_mode", sa.String(length=30), nullable=False, server_default="STANDARD"),
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "scenario_processing_mode",
        "scenario",
        "processing_mode IN ('STANDARD','PREPROCESSED_CSV')",
        schema=SCHEMA,
    )
    op.alter_column("scenario", "processing_mode", server_default=None, schema=SCHEMA)


def downgrade() -> None:
    op.drop_constraint("scenario_processing_mode", "scenario", schema=SCHEMA, type_="check")
    op.drop_column("scenario", "processing_mode", schema=SCHEMA)
