"""move change requests to osemosys values and add parameter value audit

Revision ID: 20260219_0014
Revises: 20260219_0013
Create Date: 2026-02-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260219_0014"
down_revision = "20260219_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Se reinicia histórico legacy de solicitudes sobre parameter_value
    # para migrar el workflow a osemosys_param_value sin inconsistencias de FK.
    op.execute("DELETE FROM osemosys.change_request_value")
    op.execute("DELETE FROM osemosys.change_request")

    op.drop_constraint(
        "change_request_id_parameter_value_fkey",
        "change_request",
        schema="osemosys",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_change_request_id_parameter_value",
        table_name="change_request",
        schema="osemosys",
    )
    op.alter_column(
        "change_request",
        "id_parameter_value",
        new_column_name="id_osemosys_param_value",
        schema="osemosys",
    )
    op.create_foreign_key(
        "change_request_id_osemosys_param_value_fkey",
        "change_request",
        "osemosys_param_value",
        ["id_osemosys_param_value"],
        ["id"],
        source_schema="osemosys",
        referent_schema="osemosys",
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_change_request_id_osemosys_param_value",
        "change_request",
        ["id_osemosys_param_value"],
        unique=False,
        schema="osemosys",
    )

    op.create_table(
        "parameter_value_audit",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("id_parameter_value", sa.Integer(), nullable=False),
        sa.Column("old_value", sa.Float(), nullable=False),
        sa.Column("new_value", sa.Float(), nullable=False),
        sa.Column("changed_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["id_parameter_value"],
            ["osemosys.parameter_value.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="osemosys",
    )


def downgrade() -> None:
    op.drop_table("parameter_value_audit", schema="osemosys")

    op.drop_index(
        "ix_change_request_id_osemosys_param_value",
        table_name="change_request",
        schema="osemosys",
    )
    op.drop_constraint(
        "change_request_id_osemosys_param_value_fkey",
        "change_request",
        schema="osemosys",
        type_="foreignkey",
    )
    op.alter_column(
        "change_request",
        "id_osemosys_param_value",
        new_column_name="id_parameter_value",
        schema="osemosys",
    )
    op.create_foreign_key(
        "change_request_id_parameter_value_fkey",
        "change_request",
        "parameter_value",
        ["id_parameter_value"],
        ["id"],
        source_schema="osemosys",
        referent_schema="osemosys",
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_change_request_id_parameter_value",
        "change_request",
        ["id_parameter_value"],
        unique=False,
        schema="osemosys",
    )

