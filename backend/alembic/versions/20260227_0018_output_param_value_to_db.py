"""Replace output_parameter_value with osemosys_output_param_value and add
summary columns to simulation_job so results live in PostgreSQL instead of
JSON files on disk.

Revision ID: 20260227_0018
Revises: 20260227_0017
Create Date: 2026-02-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260227_0018"
down_revision = "20260227_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop the unused output_parameter_value table.
    op.drop_table("output_parameter_value", schema="osemosys")

    # 2. Add summary / metadata columns to simulation_job.
    op.add_column("simulation_job", sa.Column("objective_value", sa.Float(), nullable=True), schema="osemosys")
    op.add_column("simulation_job", sa.Column("coverage_ratio", sa.Float(), nullable=True), schema="osemosys")
    op.add_column("simulation_job", sa.Column("total_demand", sa.Float(), nullable=True), schema="osemosys")
    op.add_column("simulation_job", sa.Column("total_dispatch", sa.Float(), nullable=True), schema="osemosys")
    op.add_column("simulation_job", sa.Column("total_unmet", sa.Float(), nullable=True), schema="osemosys")
    op.add_column("simulation_job", sa.Column("records_used", sa.Integer(), nullable=True), schema="osemosys")
    op.add_column("simulation_job", sa.Column("osemosys_param_records", sa.Integer(), nullable=True), schema="osemosys")
    op.add_column(
        "simulation_job",
        sa.Column("stage_times_json", sa.dialects.postgresql.JSONB(), nullable=True),
        schema="osemosys",
    )
    op.add_column(
        "simulation_job",
        sa.Column("model_timings_json", sa.dialects.postgresql.JSONB(), nullable=True),
        schema="osemosys",
    )
    op.add_column(
        "simulation_job",
        sa.Column("inputs_summary_json", sa.dialects.postgresql.JSONB(), nullable=True),
        schema="osemosys",
    )

    # 3. Create the new results table.
    op.create_table(
        "osemosys_output_param_value",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "id_simulation_job",
            sa.Integer(),
            sa.ForeignKey("osemosys.simulation_job.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("variable_name", sa.String(128), nullable=False),
        sa.Column("id_region", sa.Integer(), nullable=True),
        sa.Column("id_technology", sa.Integer(), nullable=True),
        sa.Column("technology_name", sa.String(128), nullable=True),
        sa.Column("fuel_name", sa.String(128), nullable=True),
        sa.Column("emission_name", sa.String(128), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("value2", sa.Float(), nullable=True),
        sa.Column("index_json", sa.dialects.postgresql.JSONB(), nullable=True),
        schema="osemosys",
    )
    op.create_index(
        "ix_oopv_simulation_job",
        "osemosys_output_param_value",
        ["id_simulation_job"],
        schema="osemosys",
    )
    op.create_index(
        "ix_oopv_job_variable",
        "osemosys_output_param_value",
        ["id_simulation_job", "variable_name"],
        schema="osemosys",
    )


def downgrade() -> None:
    op.drop_index("ix_oopv_job_variable", table_name="osemosys_output_param_value", schema="osemosys")
    op.drop_index("ix_oopv_simulation_job", table_name="osemosys_output_param_value", schema="osemosys")
    op.drop_table("osemosys_output_param_value", schema="osemosys")

    for col in (
        "inputs_summary_json", "model_timings_json", "stage_times_json",
        "osemosys_param_records", "records_used",
        "total_unmet", "total_dispatch", "total_demand",
        "coverage_ratio", "objective_value",
    ):
        op.drop_column("simulation_job", col, schema="osemosys")

    op.create_table(
        "output_parameter_value",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "id_parameter_value",
            sa.Integer(),
            sa.ForeignKey("osemosys.parameter_value.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "id_simulation_job",
            sa.Integer(),
            sa.ForeignKey("osemosys.simulation_job.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("solver_name", sa.String(20), nullable=False, server_default="highs"),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("id_parameter_value", "id_simulation_job", name="output_parameter_value_parameter_job"),
        schema="osemosys",
    )
    op.create_index("ix_output_parameter_value_id_parameter_value", "output_parameter_value", ["id_parameter_value"], schema="osemosys")
    op.create_index("ix_output_parameter_value_id_simulation_job", "output_parameter_value", ["id_simulation_job"], schema="osemosys")
