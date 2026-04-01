"""osemosys_param_value_audit table

Revision ID: 20260331_0026
Revises: 20260330_0025
Create Date: 2026-03-31
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260331_0026"
down_revision = "20260330_0025"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.create_table(
        "osemosys_param_value_audit",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("id_scenario", sa.Integer(), nullable=False),
        sa.Column("param_name", sa.String(length=128), nullable=False),
        sa.Column("id_osemosys_param_value", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("old_value", sa.Float(), nullable=True),
        sa.Column("new_value", sa.Float(), nullable=True),
        sa.Column("dimensions_json", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("changed_by", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('INSERT','UPDATE','DELETE')",
            name="ck_osemosys_param_value_audit_action",
        ),
        sa.CheckConstraint(
            "source IN ('API','EXCEL_APPLY','IMPORT_UPSERT')",
            name="ck_osemosys_param_value_audit_source",
        ),
        sa.ForeignKeyConstraint(
            ["id_osemosys_param_value"],
            [f"{SCHEMA}.osemosys_param_value.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["id_scenario"],
            [f"{SCHEMA}.scenario.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_osemosys_param_audit_scenario_param_created",
        "osemosys_param_value_audit",
        ["id_scenario", "param_name", "created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_osemosys_param_audit_scenario_param_created",
        table_name="osemosys_param_value_audit",
        schema=SCHEMA,
    )
    op.drop_table("osemosys_param_value_audit", schema=SCHEMA)
