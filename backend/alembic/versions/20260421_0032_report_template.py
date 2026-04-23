"""report_template (reportes guardados, colecciones de gráficas con orden)

Revision ID: 20260421_0032
Revises: 20260421_0031
Create Date: 2026-04-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260421_0032"
down_revision = "20260421_0031"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.create_table(
        "report_template",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("fmt", sa.String(length=8), nullable=False, server_default="png"),
        # Lista ordenada de IDs de saved_chart_template.
        sa.Column(
            "items",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_report_template_user_id",
        "report_template",
        "user",
        ["user_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema="core",
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_report_template_user_created",
        "report_template",
        ["user_id", "created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_report_template_user_created",
        table_name="report_template",
        schema=SCHEMA,
    )
    op.drop_constraint(
        "fk_report_template_user_id",
        "report_template",
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_table("report_template", schema=SCHEMA)
