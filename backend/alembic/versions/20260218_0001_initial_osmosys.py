"""initial osmosys schema

Revision ID: 20260218_0001
Revises: 
Create Date: 2026-02-18

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260218_0001"
down_revision = None
branch_labels = None
depends_on = None


SCHEMA = "osmosys"


def upgrade() -> None:
    op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))

    op.create_table(
        "scenario",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(length=255), nullable=False),
        sa.Column("edit_policy", sa.String(length=20), nullable=False, server_default="OWNER_ONLY"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "edit_policy IN ('OWNER_ONLY','OPEN','RESTRICTED')",
            name="scenario_edit_policy",
        ),
        schema=SCHEMA,
    )

    op.create_table(
        "parameter",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("name", name="parameter_name"),
        schema=SCHEMA,
    )

    op.create_table(
        "region",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("name", name="region_name"),
        schema=SCHEMA,
    )

    op.create_table(
        "technology",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("name", name="technology_name"),
        schema=SCHEMA,
    )

    op.create_table(
        "fuel",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("name", name="fuel_name"),
        schema=SCHEMA,
    )

    op.create_table(
        "emission",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("name", name="emission_name"),
        schema=SCHEMA,
    )

    op.create_table(
        "solver",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("name", name="solver_name"),
        schema=SCHEMA,
    )

    op.create_table(
        "parameter_value",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("id_scenario", sa.Integer(), nullable=False),
        sa.Column("id_parameter", sa.Integer(), nullable=False),
        sa.Column("id_region", sa.Integer(), nullable=False),
        sa.Column("id_technology", sa.Integer(), nullable=True),
        sa.Column("id_fuel", sa.Integer(), nullable=True),
        sa.Column("id_emission", sa.Integer(), nullable=True),
        sa.Column("id_solver", sa.Integer(), nullable=False),
        sa.Column("mode_of_operation", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["id_scenario"], [f"{SCHEMA}.scenario.id"], ondelete="RESTRICT", name="parameter_value_id_scenario_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["id_parameter"], [f"{SCHEMA}.parameter.id"], ondelete="RESTRICT", name="parameter_value_id_parameter_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["id_region"], [f"{SCHEMA}.region.id"], ondelete="RESTRICT", name="parameter_value_id_region_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["id_technology"], [f"{SCHEMA}.technology.id"], ondelete="RESTRICT", name="parameter_value_id_technology_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["id_fuel"], [f"{SCHEMA}.fuel.id"], ondelete="RESTRICT", name="parameter_value_id_fuel_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["id_emission"], [f"{SCHEMA}.emission.id"], ondelete="RESTRICT", name="parameter_value_id_emission_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["id_solver"], [f"{SCHEMA}.solver.id"], ondelete="RESTRICT", name="parameter_value_id_solver_fkey"
        ),
        schema=SCHEMA,
    )

    op.create_index("ix_parameter_value_id_scenario", "parameter_value", ["id_scenario"], schema=SCHEMA)
    op.create_index("ix_parameter_value_id_parameter", "parameter_value", ["id_parameter"], schema=SCHEMA)
    op.create_index("ix_parameter_value_id_region", "parameter_value", ["id_region"], schema=SCHEMA)
    op.create_index("ix_parameter_value_id_technology", "parameter_value", ["id_technology"], schema=SCHEMA)
    op.create_index("ix_parameter_value_id_fuel", "parameter_value", ["id_fuel"], schema=SCHEMA)
    op.create_index("ix_parameter_value_id_emission", "parameter_value", ["id_emission"], schema=SCHEMA)
    op.create_index("ix_parameter_value_id_solver", "parameter_value", ["id_solver"], schema=SCHEMA)
    op.create_index(
        "ix_parameter_value_scenario_parameter_year",
        "parameter_value",
        ["id_scenario", "id_parameter", "year"],
        schema=SCHEMA,
    )

    op.create_table(
        "parameter_storage",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("id_parameter_value", sa.Integer(), nullable=False),
        sa.Column("timesline", sa.Integer(), nullable=False),
        sa.Column("daytype", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("dailytimebracket", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["id_parameter_value"],
            [f"{SCHEMA}.parameter_value.id"],
            ondelete="RESTRICT",
            name="parameter_storage_id_parameter_value_fkey",
        ),
        sa.UniqueConstraint("id_parameter_value", name="parameter_storage_id_parameter_value"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_parameter_storage_id_parameter_value",
        "parameter_storage",
        ["id_parameter_value"],
        schema=SCHEMA,
    )

    op.create_table(
        "output_parameter_value",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("id_parameter_value", sa.Integer(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["id_parameter_value"],
            [f"{SCHEMA}.parameter_value.id"],
            ondelete="RESTRICT",
            name="output_parameter_value_id_parameter_value_fkey",
        ),
        sa.UniqueConstraint("id_parameter_value", name="output_parameter_value_id_parameter_value"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_output_parameter_value_id_parameter_value",
        "output_parameter_value",
        ["id_parameter_value"],
        schema=SCHEMA,
    )

    op.create_table(
        "scenario_permission",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("id_scenario", sa.Integer(), nullable=False),
        sa.Column("user_identifier", sa.String(length=255), nullable=False),
        sa.Column("can_edit_direct", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("can_propose", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(
            ["id_scenario"],
            [f"{SCHEMA}.scenario.id"],
            ondelete="RESTRICT",
            name="scenario_permission_id_scenario_fkey",
        ),
        sa.UniqueConstraint("id_scenario", "user_identifier", name="scenario_permission_scenario_user"),
        schema=SCHEMA,
    )
    op.create_index("ix_scenario_permission_id_scenario", "scenario_permission", ["id_scenario"], schema=SCHEMA)
    op.create_index(
        "ix_scenario_permission_user_identifier",
        "scenario_permission",
        ["user_identifier"],
        schema=SCHEMA,
    )

    op.create_table(
        "change_request",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("id_parameter_value", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED')",
            name="change_request_status",
        ),
        sa.ForeignKeyConstraint(
            ["id_parameter_value"],
            [f"{SCHEMA}.parameter_value.id"],
            ondelete="RESTRICT",
            name="change_request_id_parameter_value_fkey",
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_change_request_id_parameter_value", "change_request", ["id_parameter_value"], schema=SCHEMA)
    op.create_index("ix_change_request_status", "change_request", ["status"], schema=SCHEMA)

    op.create_table(
        "change_request_value",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("id_change_request", sa.Integer(), nullable=False),
        sa.Column("old_value", sa.Float(), nullable=False),
        sa.Column("new_value", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["id_change_request"],
            [f"{SCHEMA}.change_request.id"],
            ondelete="RESTRICT",
            name="change_request_value_id_change_request_fkey",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_change_request_value_id_change_request",
        "change_request_value",
        ["id_change_request"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_change_request_value_id_change_request", table_name="change_request_value", schema=SCHEMA)
    op.drop_table("change_request_value", schema=SCHEMA)

    op.drop_index("ix_change_request_status", table_name="change_request", schema=SCHEMA)
    op.drop_index("ix_change_request_id_parameter_value", table_name="change_request", schema=SCHEMA)
    op.drop_table("change_request", schema=SCHEMA)

    op.drop_index("ix_scenario_permission_user_identifier", table_name="scenario_permission", schema=SCHEMA)
    op.drop_index("ix_scenario_permission_id_scenario", table_name="scenario_permission", schema=SCHEMA)
    op.drop_table("scenario_permission", schema=SCHEMA)

    op.drop_index(
        "ix_output_parameter_value_id_parameter_value", table_name="output_parameter_value", schema=SCHEMA
    )
    op.drop_table("output_parameter_value", schema=SCHEMA)

    op.drop_index("ix_parameter_storage_id_parameter_value", table_name="parameter_storage", schema=SCHEMA)
    op.drop_table("parameter_storage", schema=SCHEMA)

    op.drop_index("ix_parameter_value_scenario_parameter_year", table_name="parameter_value", schema=SCHEMA)
    op.drop_index("ix_parameter_value_id_solver", table_name="parameter_value", schema=SCHEMA)
    op.drop_index("ix_parameter_value_id_emission", table_name="parameter_value", schema=SCHEMA)
    op.drop_index("ix_parameter_value_id_fuel", table_name="parameter_value", schema=SCHEMA)
    op.drop_index("ix_parameter_value_id_technology", table_name="parameter_value", schema=SCHEMA)
    op.drop_index("ix_parameter_value_id_region", table_name="parameter_value", schema=SCHEMA)
    op.drop_index("ix_parameter_value_id_parameter", table_name="parameter_value", schema=SCHEMA)
    op.drop_index("ix_parameter_value_id_scenario", table_name="parameter_value", schema=SCHEMA)
    op.drop_table("parameter_value", schema=SCHEMA)

    op.drop_table("solver", schema=SCHEMA)
    op.drop_table("emission", schema=SCHEMA)
    op.drop_table("fuel", schema=SCHEMA)
    op.drop_table("technology", schema=SCHEMA)
    op.drop_table("region", schema=SCHEMA)
    op.drop_table("parameter", schema=SCHEMA)
    op.drop_table("scenario", schema=SCHEMA)

    op.execute(sa.text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Crear esquema base `osmosys` y entidades iniciales del dominio.
#
# Posibles mejoras:
# - Dividir en migraciones más pequeñas para reducir riesgo operativo.
#
# Riesgos en producción:
# - `downgrade` elimina esquema completo con `CASCADE`.
#
# Escalabilidad:
# - Migración pesada, ejecutar en ventanas controladas.

