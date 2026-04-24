"""Extend osemosys_output_param_value with extra typed dimension columns.

Permite persistir TODAS las variables del modelo abstracto (RateOfActivity a
nivel timeslice, AnnualTechnologyEmissionByMode, variables de storage, etc.)
en columnas indexables en lugar de índices posicionales en index_json.

Revision ID: 20260424_0007
Revises: 20260424_0006
Create Date: 2026-04-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260424_0007"
down_revision = "20260424_0006"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"
TABLE = "osemosys_output_param_value"

NEW_COLUMNS = (
    "id_fuel",
    "id_emission",
    "id_timeslice",
    "id_mode_of_operation",
    "id_storage",
    "id_season",
    "id_daytype",
    "id_dailytimebracket",
)


def upgrade() -> None:
    for col in NEW_COLUMNS:
        op.add_column(TABLE, sa.Column(col, sa.Integer(), nullable=True), schema=SCHEMA)

    op.create_index(
        "ix_oopv_job_var_region_year",
        TABLE,
        ["id_simulation_job", "variable_name", "id_region", "year"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_oopv_job_var_tech",
        TABLE,
        ["id_simulation_job", "variable_name", "id_technology"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_oopv_job_var_tech", table_name=TABLE, schema=SCHEMA)
    op.drop_index("ix_oopv_job_var_region_year", table_name=TABLE, schema=SCHEMA)
    for col in reversed(NEW_COLUMNS):
        op.drop_column(TABLE, col, schema=SCHEMA)
