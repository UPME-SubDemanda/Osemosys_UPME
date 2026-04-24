"""user.is_admin_reports + favoritos de chart templates y reports

Revision ID: 20260423_0004
Revises: 20260423_0003
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260423_0004"
down_revision = "20260423_0003"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    # Nuevo permiso en core.user
    op.add_column(
        "user",
        sa.Column(
            "is_admin_reports",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema="core",
    )

    # Favoritos de plantillas de gráfica (per-user)
    op.create_table(
        "saved_chart_template_favorite",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id", "template_id"),
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_saved_chart_template_favorite_user_id",
        "saved_chart_template_favorite",
        "user",
        ["user_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema="core",
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_saved_chart_template_favorite_template_id",
        "saved_chart_template_favorite",
        "saved_chart_template",
        ["template_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_saved_chart_template_favorite_template_id",
        "saved_chart_template_favorite",
        ["template_id"],
        schema=SCHEMA,
    )

    # Favoritos de reportes (per-user)
    op.create_table(
        "report_template_favorite",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id", "report_id"),
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_report_template_favorite_user_id",
        "report_template_favorite",
        "user",
        ["user_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema="core",
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_report_template_favorite_report_id",
        "report_template_favorite",
        "report_template",
        ["report_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_report_template_favorite_report_id",
        "report_template_favorite",
        ["report_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_report_template_favorite_report_id",
        table_name="report_template_favorite",
        schema=SCHEMA,
    )
    op.drop_constraint(
        "fk_report_template_favorite_report_id",
        "report_template_favorite",
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_report_template_favorite_user_id",
        "report_template_favorite",
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_table("report_template_favorite", schema=SCHEMA)

    op.drop_index(
        "ix_saved_chart_template_favorite_template_id",
        table_name="saved_chart_template_favorite",
        schema=SCHEMA,
    )
    op.drop_constraint(
        "fk_saved_chart_template_favorite_template_id",
        "saved_chart_template_favorite",
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_saved_chart_template_favorite_user_id",
        "saved_chart_template_favorite",
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_table("saved_chart_template_favorite", schema=SCHEMA)

    op.drop_column("user", "is_admin_reports", schema="core")
