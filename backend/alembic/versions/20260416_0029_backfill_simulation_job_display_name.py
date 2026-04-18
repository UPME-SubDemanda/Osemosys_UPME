"""Rellena display_name existente con nombre de escenario (o input CSV).

Revision ID: 20260416_0029
Revises: 20260415_0028
Create Date: 2026-04-16
"""

from __future__ import annotations

from alembic import op

revision = "20260416_0029"
down_revision = "20260415_0028"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    # Jobs ligados a escenario: copiar nombre del escenario.
    op.execute(
        f"""
        UPDATE {SCHEMA}.simulation_job sj
        SET display_name = LEFT(TRIM(s.name), 255)
        FROM {SCHEMA}.scenario s
        WHERE sj.display_name IS NULL
          AND sj.scenario_id IS NOT NULL
          AND sj.scenario_id = s.id
          AND s.name IS NOT NULL
          AND TRIM(s.name) <> ''
        """
    )
    # Importación CSV sin escenario: usar input_name si existe.
    op.execute(
        f"""
        UPDATE {SCHEMA}.simulation_job
        SET display_name = LEFT(TRIM(input_name), 255)
        WHERE display_name IS NULL
          AND scenario_id IS NULL
          AND input_mode = 'CSV_UPLOAD'
          AND input_name IS NOT NULL
          AND TRIM(input_name) <> ''
        """
    )


def downgrade() -> None:
    # Migración de datos: no se revierte de forma segura.
    pass
