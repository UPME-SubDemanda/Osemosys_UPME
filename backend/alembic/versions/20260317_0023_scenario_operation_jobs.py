"""scenario operation jobs

Revision ID: 20260317_0023
Revises: 20260316_0022
Create Date: 2026-03-17
"""

from alembic import op
import sqlalchemy as sa


revision = "20260317_0023"
down_revision = "20260316_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scenario_operation_job",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("operation_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.Integer(), nullable=True),
        sa.Column("target_scenario_id", sa.Integer(), nullable=True),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("stage", sa.String(length=80), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED')",
            name="scenario_operation_job_status",
        ),
        sa.CheckConstraint(
            "operation_type IN ('CLONE_SCENARIO','APPLY_EXCEL_CHANGES')",
            name="scenario_operation_job_type",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["core.user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["scenario_id"], ["osemosys.scenario.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_scenario_id"], ["osemosys.scenario.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        schema="osemosys",
    )
    op.create_index(
        "ix_scenario_operation_job_user_status",
        "scenario_operation_job",
        ["user_id", "status"],
        unique=False,
        schema="osemosys",
    )
    op.create_index(
        "ix_scenario_operation_job_scenario",
        "scenario_operation_job",
        ["scenario_id"],
        unique=False,
        schema="osemosys",
    )

    op.create_table(
        "scenario_operation_job_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("stage", sa.String(length=80), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("progress", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["osemosys.scenario_operation_job.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema="osemosys",
    )
    op.create_index(
        "ix_scenario_operation_event_job_id",
        "scenario_operation_job_event",
        ["job_id"],
        unique=False,
        schema="osemosys",
    )
    op.create_index(
        "ix_scenario_operation_event_job_created",
        "scenario_operation_job_event",
        ["job_id", "created_at"],
        unique=False,
        schema="osemosys",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_scenario_operation_event_job_created",
        table_name="scenario_operation_job_event",
        schema="osemosys",
    )
    op.drop_index(
        "ix_scenario_operation_event_job_id",
        table_name="scenario_operation_job_event",
        schema="osemosys",
    )
    op.drop_table("scenario_operation_job_event", schema="osemosys")

    op.drop_index(
        "ix_scenario_operation_job_scenario",
        table_name="scenario_operation_job",
        schema="osemosys",
    )
    op.drop_index(
        "ix_scenario_operation_job_user_status",
        table_name="scenario_operation_job",
        schema="osemosys",
    )
    op.drop_table("scenario_operation_job", schema="osemosys")
