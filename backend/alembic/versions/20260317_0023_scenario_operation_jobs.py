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


SCHEMA = "osemosys"


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return table_name in _inspector().get_table_names(schema=SCHEMA)


def _index_exists(table_name: str, index_name: str) -> bool:
    indexes = _inspector().get_indexes(table_name, schema=SCHEMA)
    return any(index["name"] == index_name for index in indexes)


def upgrade() -> None:
    if not _table_exists("scenario_operation_job"):
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
            schema=SCHEMA,
        )

    if not _index_exists("scenario_operation_job", "ix_scenario_operation_job_user_status"):
        op.create_index(
            "ix_scenario_operation_job_user_status",
            "scenario_operation_job",
            ["user_id", "status"],
            unique=False,
            schema=SCHEMA,
        )
    if not _index_exists("scenario_operation_job", "ix_scenario_operation_job_scenario"):
        op.create_index(
            "ix_scenario_operation_job_scenario",
            "scenario_operation_job",
            ["scenario_id"],
            unique=False,
            schema=SCHEMA,
        )

    if not _table_exists("scenario_operation_job_event"):
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
            schema=SCHEMA,
        )

    if not _index_exists("scenario_operation_job_event", "ix_scenario_operation_event_job_id"):
        op.create_index(
            "ix_scenario_operation_event_job_id",
            "scenario_operation_job_event",
            ["job_id"],
            unique=False,
            schema=SCHEMA,
        )
    if not _index_exists("scenario_operation_job_event", "ix_scenario_operation_event_job_created"):
        op.create_index(
            "ix_scenario_operation_event_job_created",
            "scenario_operation_job_event",
            ["job_id", "created_at"],
            unique=False,
            schema=SCHEMA,
        )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS osemosys.ix_scenario_operation_event_job_created"))
    op.execute(sa.text("DROP INDEX IF EXISTS osemosys.ix_scenario_operation_event_job_id"))
    op.execute(sa.text("DROP TABLE IF EXISTS osemosys.scenario_operation_job_event"))

    op.execute(sa.text("DROP INDEX IF EXISTS osemosys.ix_scenario_operation_job_scenario"))
    op.execute(sa.text("DROP INDEX IF EXISTS osemosys.ix_scenario_operation_job_user_status"))
    op.execute(sa.text("DROP TABLE IF EXISTS osemosys.scenario_operation_job"))
