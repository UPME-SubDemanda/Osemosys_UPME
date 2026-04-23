"""is_public on saved_chart_template + is_public/is_official on report_template

Revision ID: 20260421_0033
Revises: 20260421_0032
Create Date: 2026-04-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260421_0033"
down_revision = "20260421_0032"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.add_column(
        "saved_chart_template",
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_saved_chart_template_is_public",
        "saved_chart_template",
        ["is_public"],
        schema=SCHEMA,
    )

    op.add_column(
        "report_template",
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "report_template",
        sa.Column(
            "is_official",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_report_template_visibility",
        "report_template",
        ["is_public", "is_official"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_report_template_visibility",
        table_name="report_template",
        schema=SCHEMA,
    )
    op.drop_column("report_template", "is_official", schema=SCHEMA)
    op.drop_column("report_template", "is_public", schema=SCHEMA)

    op.drop_index(
        "ix_saved_chart_template_is_public",
        table_name="saved_chart_template",
        schema=SCHEMA,
    )
    op.drop_column("saved_chart_template", "is_public", schema=SCHEMA)
