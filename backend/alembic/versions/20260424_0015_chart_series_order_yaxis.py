"""saved_chart_template: custom_series_order, y_axis_min, y_axis_max.

Modificadores persistidos por plantilla — antes vivían solo como state local
en la UI de Resultados, así que se perdían al guardar/exportar/compartir.

Revision ID: 20260424_0015
Revises: 20260424_0014
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260424_0015"
down_revision = "20260424_0014"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    op.add_column(
        "saved_chart_template",
        sa.Column("custom_series_order", JSONB(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "saved_chart_template",
        sa.Column("y_axis_min", sa.Float(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "saved_chart_template",
        sa.Column("y_axis_max", sa.Float(), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("saved_chart_template", "y_axis_max", schema=SCHEMA)
    op.drop_column("saved_chart_template", "y_axis_min", schema=SCHEMA)
    op.drop_column("saved_chart_template", "custom_series_order", schema=SCHEMA)
