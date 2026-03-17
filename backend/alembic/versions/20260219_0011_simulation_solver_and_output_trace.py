"""add solver selection and output trace columns

Revision ID: 20260219_0011
Revises: 20260219_0010
Create Date: 2026-02-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260219_0011"
down_revision = "20260219_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "simulation_job",
        sa.Column("solver_name", sa.String(length=20), nullable=False, server_default="highs"),
        schema="osemosys",
    )

    op.add_column(
        "output_parameter_value",
        sa.Column("id_simulation_job", sa.Integer(), nullable=True),
        schema="osemosys",
    )
    op.add_column(
        "output_parameter_value",
        sa.Column("solver_name", sa.String(length=20), nullable=False, server_default="highs"),
        schema="osemosys",
    )
    op.create_foreign_key(
        "fk_output_parameter_value_simulation_job",
        "output_parameter_value",
        "simulation_job",
        ["id_simulation_job"],
        ["id"],
        source_schema="osemosys",
        referent_schema="osemosys",
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "output_parameter_value_id_parameter_value",
        "output_parameter_value",
        schema="osemosys",
        type_="unique",
    )
    op.create_unique_constraint(
        "output_parameter_value_parameter_job",
        "output_parameter_value",
        ["id_parameter_value", "id_simulation_job"],
        schema="osemosys",
    )
    op.create_index(
        "ix_output_parameter_value_id_simulation_job",
        "output_parameter_value",
        ["id_simulation_job"],
        unique=False,
        schema="osemosys",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_output_parameter_value_id_simulation_job",
        table_name="output_parameter_value",
        schema="osemosys",
    )
    op.drop_constraint(
        "output_parameter_value_parameter_job",
        "output_parameter_value",
        schema="osemosys",
        type_="unique",
    )
    op.create_unique_constraint(
        "output_parameter_value_id_parameter_value",
        "output_parameter_value",
        ["id_parameter_value"],
        schema="osemosys",
    )
    op.drop_constraint(
        "fk_output_parameter_value_simulation_job",
        "output_parameter_value",
        schema="osemosys",
        type_="foreignkey",
    )
    op.drop_column("output_parameter_value", "solver_name", schema="osemosys")
    op.drop_column("output_parameter_value", "id_simulation_job", schema="osemosys")
    op.drop_column("simulation_job", "solver_name", schema="osemosys")

