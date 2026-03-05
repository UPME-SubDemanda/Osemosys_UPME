"""add simulation jobs and job events

Revision ID: 20260218_0007
Revises: 20260218_0006
Create Date: 2026-02-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260218_0007"
down_revision = "20260218_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "simulation_job",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scenario_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="QUEUED"),
        sa.Column("progress", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("result_ref", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED')",
            name="simulation_job_status",
        ),
        sa.ForeignKeyConstraint(["scenario_id"], ["osmosys.scenario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["core.user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        schema="osmosys",
    )
    op.create_index(
        "ix_simulation_job_user_status",
        "simulation_job",
        ["user_id", "status"],
        schema="osmosys",
    )
    op.create_index("ix_simulation_job_scenario", "simulation_job", ["scenario_id"], schema="osmosys")

    op.create_table(
        "simulation_job_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False, server_default="INFO"),
        sa.Column("stage", sa.String(length=50), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("progress", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["osmosys.simulation_job.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema="osmosys",
    )
    op.create_index(
        "ix_simulation_job_event_job_id",
        "simulation_job_event",
        ["job_id"],
        schema="osmosys",
    )
    op.create_index(
        "ix_simulation_job_event_job_created_at",
        "simulation_job_event",
        ["job_id", "created_at"],
        schema="osmosys",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_simulation_job_event_job_created_at",
        table_name="simulation_job_event",
        schema="osmosys",
    )
    op.drop_index(
        "ix_simulation_job_event_job_id",
        table_name="simulation_job_event",
        schema="osmosys",
    )
    op.drop_table("simulation_job_event", schema="osmosys")

    op.drop_index("ix_simulation_job_scenario", table_name="simulation_job", schema="osmosys")
    op.drop_index("ix_simulation_job_user_status", table_name="simulation_job", schema="osmosys")
    op.drop_table("simulation_job", schema="osmosys")


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Crear tablas de jobs/eventos para ejecución asíncrona de simulaciones.
#
# Posibles mejoras:
# - Particionado temporal en eventos para retención eficiente.
#
# Riesgos en producción:
# - Alto volumen de eventos puede requerir política de limpieza.
#
# Escalabilidad:
# - Diseñado para concurrencia moderada; índices clave por `user/status` y `job_id`.
