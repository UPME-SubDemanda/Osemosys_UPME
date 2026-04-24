"""report_template.default_job_ids — escenarios por defecto por reporte.

Revision ID: 20260424_0005
Revises: 20260424_0004
Create Date: 2026-04-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260424_0005"
down_revision = "20260424_0004"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.add_column(
        "report_template",
        sa.Column("default_job_ids", JSONB(), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("report_template", "default_job_ids", schema=SCHEMA)
