"""add osemosys sets and multidimensional parameter table

Revision ID: 20260218_0008
Revises: 20260218_0007
Create Date: 2026-02-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260218_0008"
down_revision = "20260218_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "timeslice",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="timeslice_code"),
        schema="osmosys",
    )

    op.create_table(
        "mode_of_operation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="mode_of_operation_code"),
        schema="osmosys",
    )

    op.create_table(
        "season",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="season_code"),
        schema="osmosys",
    )

    op.create_table(
        "daytype",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="daytype_code"),
        schema="osmosys",
    )

    op.create_table(
        "dailytimebracket",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="dailytimebracket_code"),
        schema="osmosys",
    )

    op.create_table(
        "storage_set",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="storage_set_code"),
        schema="osmosys",
    )

    op.create_table(
        "udc_set",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="udc_set_code"),
        schema="osmosys",
    )

    op.create_table(
        "osemosys_param_value",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("id_scenario", sa.Integer(), nullable=False),
        sa.Column("param_name", sa.String(length=128), nullable=False),
        sa.Column("id_region", sa.Integer(), nullable=True),
        sa.Column("id_technology", sa.Integer(), nullable=True),
        sa.Column("id_fuel", sa.Integer(), nullable=True),
        sa.Column("id_emission", sa.Integer(), nullable=True),
        sa.Column("id_timeslice", sa.Integer(), nullable=True),
        sa.Column("id_mode_of_operation", sa.Integer(), nullable=True),
        sa.Column("id_season", sa.Integer(), nullable=True),
        sa.Column("id_daytype", sa.Integer(), nullable=True),
        sa.Column("id_dailytimebracket", sa.Integer(), nullable=True),
        sa.Column("id_storage_set", sa.Integer(), nullable=True),
        sa.Column("id_udc_set", sa.Integer(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("value", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["id_scenario"], ["osmosys.scenario.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["id_region"], ["osmosys.region.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["id_technology"], ["osmosys.technology.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["id_fuel"], ["osmosys.fuel.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["id_emission"], ["osmosys.emission.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["id_timeslice"], ["osmosys.timeslice.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["id_mode_of_operation"], ["osmosys.mode_of_operation.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["id_season"], ["osmosys.season.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["id_daytype"], ["osmosys.daytype.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["id_dailytimebracket"], ["osmosys.dailytimebracket.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["id_storage_set"], ["osmosys.storage_set.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["id_udc_set"], ["osmosys.udc_set.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id_scenario",
            "param_name",
            "id_region",
            "id_technology",
            "id_fuel",
            "id_emission",
            "id_timeslice",
            "id_mode_of_operation",
            "id_season",
            "id_daytype",
            "id_dailytimebracket",
            "id_storage_set",
            "id_udc_set",
            "year",
            name="uq_osemosys_param_value_dims",
        ),
        schema="osmosys",
    )
    op.create_index(
        "ix_osemosys_param_value_scenario",
        "osemosys_param_value",
        ["id_scenario"],
        schema="osmosys",
    )
    op.create_index(
        "ix_osemosys_param_value_param",
        "osemosys_param_value",
        ["param_name"],
        schema="osmosys",
    )
    op.create_index(
        "ix_osemosys_param_value_year",
        "osemosys_param_value",
        ["year"],
        schema="osmosys",
    )
    op.create_index(
        "ix_osemosys_param_value_region_tech_year",
        "osemosys_param_value",
        ["id_region", "id_technology", "year"],
        schema="osmosys",
    )

    op.create_table(
        "simulation_benchmark",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("benchmark_key", sa.String(length=128), nullable=False),
        sa.Column("scenario_name", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="notebook"),
        sa.Column("objective_value", sa.Float(), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="osmosys",
    )


def downgrade() -> None:
    op.drop_table("simulation_benchmark", schema="osmosys")
    op.drop_index(
        "ix_osemosys_param_value_region_tech_year",
        table_name="osemosys_param_value",
        schema="osmosys",
    )
    op.drop_index(
        "ix_osemosys_param_value_year",
        table_name="osemosys_param_value",
        schema="osmosys",
    )
    op.drop_index(
        "ix_osemosys_param_value_param",
        table_name="osemosys_param_value",
        schema="osmosys",
    )
    op.drop_index(
        "ix_osemosys_param_value_scenario",
        table_name="osemosys_param_value",
        schema="osmosys",
    )
    op.drop_table("osemosys_param_value", schema="osmosys")
    op.drop_table("udc_set", schema="osmosys")
    op.drop_table("storage_set", schema="osmosys")
    op.drop_table("dailytimebracket", schema="osmosys")
    op.drop_table("daytype", schema="osmosys")
    op.drop_table("season", schema="osmosys")
    op.drop_table("mode_of_operation", schema="osmosys")
    op.drop_table("timeslice", schema="osmosys")


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Introducir sets OSeMOSYS y tabla multidimensional de parámetros.
#
# Posibles mejoras:
# - Índices adicionales según patrones reales de consulta del loader.
#
# Riesgos en producción:
# - Tabla `osemosys_param_value` puede crecer rápidamente y requerir tuning/partición.
#
# Escalabilidad:
# - Migración estructural amplia; ejecutar con ventana de mantenimiento.
