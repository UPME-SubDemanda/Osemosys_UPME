"""parameter_storage defaults: nullable dims + storage_set

Revision ID: 20260302_0019
Revises: 20260227_0018
Create Date: 2026-03-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260302_0019"
down_revision = "20260227_0018"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.alter_column(
        "parameter_storage",
        "timesline",
        existing_type=sa.Integer(),
        nullable=True,
        schema=SCHEMA,
    )
    op.alter_column(
        "parameter_storage",
        "daytype",
        existing_type=sa.Integer(),
        nullable=True,
        schema=SCHEMA,
    )
    op.alter_column(
        "parameter_storage",
        "season",
        existing_type=sa.Integer(),
        nullable=True,
        schema=SCHEMA,
    )
    op.alter_column(
        "parameter_storage",
        "dailytimebracket",
        existing_type=sa.Integer(),
        nullable=True,
        schema=SCHEMA,
    )
    op.add_column(
        "parameter_storage",
        sa.Column("id_storage_set", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("parameter_storage", "id_storage_set", schema=SCHEMA)
    op.alter_column(
        "parameter_storage",
        "dailytimebracket",
        existing_type=sa.Integer(),
        nullable=False,
        schema=SCHEMA,
    )
    op.alter_column(
        "parameter_storage",
        "season",
        existing_type=sa.Integer(),
        nullable=False,
        schema=SCHEMA,
    )
    op.alter_column(
        "parameter_storage",
        "daytype",
        existing_type=sa.Integer(),
        nullable=False,
        schema=SCHEMA,
    )
    op.alter_column(
        "parameter_storage",
        "timesline",
        existing_type=sa.Integer(),
        nullable=False,
        schema=SCHEMA,
    )

