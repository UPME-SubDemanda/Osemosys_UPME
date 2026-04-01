"""support csv upload simulation jobs

Revision ID: 20260330_0025
Revises: 20260324_0024
Create Date: 2026-03-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260330_0025"
down_revision = "20260324_0024"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.alter_column(
        "simulation_job",
        "scenario_id",
        existing_type=sa.Integer(),
        nullable=True,
        schema=SCHEMA,
    )
    op.add_column(
        "simulation_job",
        sa.Column("input_mode", sa.String(length=20), nullable=False, server_default="SCENARIO"),
        schema=SCHEMA,
    )
    op.add_column(
        "simulation_job",
        sa.Column("input_name", sa.String(length=255), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "simulation_job",
        sa.Column("input_ref", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "simulation_job",
        sa.Column("infeasibility_diagnostics_json", sa.JSON(), nullable=True),
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "simulation_job_input_mode",
        "simulation_job",
        "input_mode IN ('SCENARIO','CSV_UPLOAD')",
        schema=SCHEMA,
    )
    op.alter_column(
        "simulation_job",
        "input_mode",
        server_default=None,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint("simulation_job_input_mode", "simulation_job", schema=SCHEMA, type_="check")
    op.drop_column("simulation_job", "infeasibility_diagnostics_json", schema=SCHEMA)
    op.drop_column("simulation_job", "input_ref", schema=SCHEMA)
    op.drop_column("simulation_job", "input_name", schema=SCHEMA)
    op.drop_column("simulation_job", "input_mode", schema=SCHEMA)
    op.alter_column(
        "simulation_job",
        "scenario_id",
        existing_type=sa.Integer(),
        nullable=False,
        schema=SCHEMA,
    )
