"""saved_chart_template (plantillas de gráficas guardadas por usuario)

Revision ID: 20260421_0030
Revises: 20260421_0029
Create Date: 2026-04-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260421_0030"
down_revision = "20260421_0029"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.create_table(
        "saved_chart_template",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tipo", sa.String(length=64), nullable=False),
        sa.Column("un", sa.String(length=16), nullable=False),
        sa.Column("sub_filtro", sa.String(length=64), nullable=True),
        sa.Column("loc", sa.String(length=32), nullable=True),
        sa.Column("variable", sa.String(length=64), nullable=True),
        sa.Column("agrupar_por", sa.String(length=32), nullable=True),
        sa.Column("view_mode", sa.String(length=16), nullable=True),
        sa.Column("compare_mode", sa.String(length=16), nullable=False, server_default="off"),
        sa.Column("bar_orientation", sa.String(length=16), nullable=True),
        sa.Column("facet_placement", sa.String(length=16), nullable=True),
        sa.Column("facet_legend_mode", sa.String(length=16), nullable=True),
        sa.Column("num_scenarios", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("legend_title", sa.String(length=255), nullable=True),
        sa.Column("filename_mode", sa.String(length=16), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_saved_chart_template_user_id",
        "saved_chart_template",
        "user",
        ["user_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema="core",
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_saved_chart_template_user_created",
        "saved_chart_template",
        ["user_id", "created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_saved_chart_template_user_created",
        table_name="saved_chart_template",
        schema=SCHEMA,
    )
    op.drop_constraint(
        "fk_saved_chart_template_user_id",
        "saved_chart_template",
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_table("saved_chart_template", schema=SCHEMA)
