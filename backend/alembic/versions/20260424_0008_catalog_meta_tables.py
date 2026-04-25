"""Fase 3.1 — tablas catalog_meta_* para configuración editable de visualización.

Reemplaza gradualmente los dicts hardcodeados en:
  - backend/app/visualization/configs.py (CONFIGS, DATA_EXPLORER_FILTERS,
    TITULOS_VARIABLES_CAPACIDAD, NOMBRES_COMBUSTIBLES)
  - backend/app/visualization/configs_comparacion.py (MAPA_SECTOR, COLORES_SECTOR)
  - backend/app/visualization/colors.py (FAMILIAS_TEC, COLORES_GRUPOS,
    COLOR_MAP_PWR, COLORES_EMISIONES)
  - backend/app/visualization/labels.py (DISPLAY_NAMES)
  - frontend/src/shared/charts/ChartSelector.tsx (MENU: módulos/submódulos)

Todas las tablas incluyen auditoría básica (created_at, updated_at, modified_by).

Revision ID: 20260424_0008
Revises: 20260424_0007
Create Date: 2026-04-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260424_0008"
down_revision = "20260424_0007"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def _audit_columns() -> list:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("modified_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "catalog_meta_color_palette",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("color_hex", sa.String(9), nullable=False),
        sa.Column("group", sa.String(32), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *_audit_columns(),
        sa.UniqueConstraint("group", "key", name="uq_color_palette_group_key"),
        schema=SCHEMA,
    )
    op.create_index("ix_color_palette_group", "catalog_meta_color_palette", ["group"], schema=SCHEMA)

    op.create_table(
        "catalog_meta_label",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(128), nullable=False),
        sa.Column("label_es", sa.String(255), nullable=False),
        sa.Column("label_en", sa.String(255), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *_audit_columns(),
        sa.UniqueConstraint("code", name="uq_label_code"),
        schema=SCHEMA,
    )
    op.create_index("ix_label_category", "catalog_meta_label", ["category"], schema=SCHEMA)

    op.create_table(
        "catalog_meta_sector_mapping",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tech_prefix", sa.String(64), nullable=False),
        sa.Column("sector_name", sa.String(128), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *_audit_columns(),
        sa.UniqueConstraint("tech_prefix", name="uq_sector_mapping_prefix"),
        schema=SCHEMA,
    )

    op.create_table(
        "catalog_meta_tech_family",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_code", sa.String(64), nullable=False),
        sa.Column("tech_prefix", sa.String(64), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *_audit_columns(),
        sa.UniqueConstraint("family_code", "tech_prefix", name="uq_tech_family_row"),
        schema=SCHEMA,
    )
    op.create_index("ix_tech_family_family", "catalog_meta_tech_family", ["family_code"], schema=SCHEMA)

    op.create_table(
        "catalog_meta_chart_module",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("icon", sa.String(16), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_audit_columns(),
        sa.UniqueConstraint("code", name="uq_chart_module_code"),
        schema=SCHEMA,
    )

    op.create_table(
        "catalog_meta_chart_submodule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("module_id", sa.Integer(), sa.ForeignKey("osemosys.catalog_meta_chart_module.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("icon", sa.String(16), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_audit_columns(),
        sa.UniqueConstraint("module_id", "code", name="uq_chart_submodule_code"),
        schema=SCHEMA,
    )

    op.create_table(
        "catalog_meta_chart_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tipo", sa.String(64), nullable=False),
        sa.Column("module_id", sa.Integer(), sa.ForeignKey("osemosys.catalog_meta_chart_module.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("submodule_id", sa.Integer(), sa.ForeignKey("osemosys.catalog_meta_chart_submodule.id", ondelete="SET NULL"), nullable=True),
        sa.Column("label_titulo", sa.String(255), nullable=False),
        sa.Column("label_figura", sa.String(64), nullable=True),
        sa.Column("variable_default", sa.String(128), nullable=False),
        sa.Column("filtro_kind", sa.String(64), nullable=False, server_default="prefix"),
        sa.Column("filtro_params_json", postgresql.JSONB(), nullable=True),
        sa.Column("agrupar_por_default", sa.String(32), nullable=False, server_default="TECNOLOGIA"),
        sa.Column("agrupaciones_permitidas_json", postgresql.JSONB(), nullable=True),
        sa.Column("color_fn_key", sa.String(32), nullable=False, server_default="tecnologias"),
        sa.Column("flags_json", postgresql.JSONB(), nullable=True),
        sa.Column("msg_sin_datos", sa.String(512), nullable=True),
        sa.Column("data_explorer_filters_json", postgresql.JSONB(), nullable=True),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *_audit_columns(),
        sa.UniqueConstraint("tipo", name="uq_chart_config_tipo"),
        schema=SCHEMA,
    )
    op.create_index("ix_chart_config_module", "catalog_meta_chart_config", ["module_id"], schema=SCHEMA)
    op.create_index("ix_chart_config_submodule", "catalog_meta_chart_config", ["submodule_id"], schema=SCHEMA)

    op.create_table(
        "catalog_meta_chart_subfilter",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chart_id", sa.Integer(), sa.ForeignKey("osemosys.catalog_meta_chart_config.id", ondelete="CASCADE"), nullable=False),
        sa.Column("group_label", sa.String(64), nullable=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("display_label", sa.String(128), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("default_selected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        *_audit_columns(),
        sa.UniqueConstraint("chart_id", "code", name="uq_chart_subfilter_code"),
        schema=SCHEMA,
    )
    op.create_index("ix_chart_subfilter_chart", "catalog_meta_chart_subfilter", ["chart_id"], schema=SCHEMA)

    op.create_table(
        "catalog_meta_chart_subfilter_group",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chart_id", sa.Integer(), sa.ForeignKey("osemosys.catalog_meta_chart_config.id", ondelete="CASCADE"), nullable=False),
        sa.Column("group_label", sa.String(128), nullable=False),
        sa.Column("subfilter_codes_json", postgresql.JSONB(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *_audit_columns(),
        schema=SCHEMA,
    )

    op.create_table(
        "catalog_meta_variable_unit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("variable_name", sa.String(128), nullable=False),
        sa.Column("unit_base", sa.String(32), nullable=False),
        sa.Column("display_units_json", postgresql.JSONB(), nullable=True),
        *_audit_columns(),
        sa.UniqueConstraint("variable_name", name="uq_variable_unit_name"),
        schema=SCHEMA,
    )

    op.create_table(
        "catalog_meta_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("table_name", sa.String(64), nullable=False),
        sa.Column("row_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("diff_json", postgresql.JSONB(), nullable=True),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema=SCHEMA,
    )
    op.create_index("ix_catalog_meta_audit_table", "catalog_meta_audit", ["table_name", "row_id"], schema=SCHEMA)


def downgrade() -> None:
    for tbl in (
        "catalog_meta_audit",
        "catalog_meta_variable_unit",
        "catalog_meta_chart_subfilter_group",
        "catalog_meta_chart_subfilter",
        "catalog_meta_chart_config",
        "catalog_meta_chart_submodule",
        "catalog_meta_chart_module",
        "catalog_meta_tech_family",
        "catalog_meta_sector_mapping",
        "catalog_meta_label",
        "catalog_meta_color_palette",
    ):
        op.drop_table(tbl, schema=SCHEMA)
