"""simulation_job.is_public + simulation_job_favorite

Revision ID: 20260421_0031
Revises: 20260421_0030
Create Date: 2026-04-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260421_0031"
down_revision = "20260421_0030"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.add_column(
        "simulation_job",
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_simulation_job_is_public",
        "simulation_job",
        ["is_public"],
        schema=SCHEMA,
    )

    op.create_table(
        "simulation_job_favorite",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id", "job_id"),
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_simulation_job_favorite_user_id",
        "simulation_job_favorite",
        "user",
        ["user_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema="core",
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_simulation_job_favorite_job_id",
        "simulation_job_favorite",
        "simulation_job",
        ["job_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_simulation_job_favorite_job_id",
        "simulation_job_favorite",
        ["job_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_simulation_job_favorite_job_id",
        table_name="simulation_job_favorite",
        schema=SCHEMA,
    )
    op.drop_constraint(
        "fk_simulation_job_favorite_job_id",
        "simulation_job_favorite",
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_simulation_job_favorite_user_id",
        "simulation_job_favorite",
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_table("simulation_job_favorite", schema=SCHEMA)

    op.drop_index(
        "ix_simulation_job_is_public",
        table_name="simulation_job",
        schema=SCHEMA,
    )
    op.drop_column("simulation_job", "is_public", schema=SCHEMA)
