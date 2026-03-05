"""add udc_config JSONB column to scenario

Revision ID: 20260227_0016
Revises: 20260225_0015
Create Date: 2026-02-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260227_0016"
down_revision = "20260225_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scenario",
        sa.Column("udc_config", JSONB, nullable=True),
        schema="osemosys",
    )


def downgrade() -> None:
    op.drop_column("scenario", "udc_config", schema="osemosys")
