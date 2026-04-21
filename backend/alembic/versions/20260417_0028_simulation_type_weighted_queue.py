"""add scenario/simulation type and weighted queue fields

Revision ID: 20260417_0028
Revises: 20260413_0027
Create Date: 2026-04-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260417_0028"
down_revision = "20260413_0027"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.add_column(
        "scenario",
        sa.Column("simulation_type", sa.String(length=20), nullable=False, server_default="NATIONAL"),
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "scenario_simulation_type",
        "scenario",
        "simulation_type IN ('NATIONAL','REGIONAL')",
        schema=SCHEMA,
    )
    op.alter_column("scenario", "simulation_type", server_default=None, schema=SCHEMA)

    op.add_column(
        "simulation_job",
        sa.Column("simulation_type", sa.String(length=20), nullable=False, server_default="NATIONAL"),
        schema=SCHEMA,
    )
    op.add_column(
        "simulation_job",
        sa.Column("parallel_weight", sa.Integer(), nullable=False, server_default="1"),
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "simulation_job_simulation_type",
        "simulation_job",
        "simulation_type IN ('NATIONAL','REGIONAL')",
        schema=SCHEMA,
    )
    op.create_index(
        "ix_simulation_job_status_queue",
        "simulation_job",
        ["status", "queued_at"],
        unique=False,
        schema=SCHEMA,
    )
    op.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA}.simulation_job
            SET parallel_weight = CASE
                WHEN simulation_type = 'REGIONAL' THEN 3
                ELSE 1
            END
            """
        )
    )
    op.alter_column("simulation_job", "simulation_type", server_default=None, schema=SCHEMA)
    op.alter_column("simulation_job", "parallel_weight", server_default=None, schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_simulation_job_status_queue", table_name="simulation_job", schema=SCHEMA)
    op.drop_constraint("simulation_job_simulation_type", "simulation_job", schema=SCHEMA, type_="check")
    op.drop_column("simulation_job", "parallel_weight", schema=SCHEMA)
    op.drop_column("simulation_job", "simulation_type", schema=SCHEMA)

    op.drop_constraint("scenario_simulation_type", "scenario", schema=SCHEMA, type_="check")
    op.drop_column("scenario", "simulation_type", schema=SCHEMA)
