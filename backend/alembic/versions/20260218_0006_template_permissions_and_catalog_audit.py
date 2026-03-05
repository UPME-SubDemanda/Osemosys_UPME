"""add template scenario, special permissions and catalog audit

Revision ID: 20260218_0006
Revises: 20260218_0005
Create Date: 2026-02-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260218_0006"
down_revision = "20260218_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scenario",
        sa.Column("is_template", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema="osmosys",
    )
    op.add_column(
        "scenario_permission",
        sa.Column("can_manage_values", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema="osmosys",
    )
    op.add_column(
        "user",
        sa.Column("can_manage_catalogs", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema="core",
    )
    op.create_table(
        "catalog_change_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("old_name", sa.Text(), nullable=True),
        sa.Column("new_name", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="osmosys",
    )


def downgrade() -> None:
    op.drop_table("catalog_change_log", schema="osmosys")
    op.drop_column("user", "can_manage_catalogs", schema="core")
    op.drop_column("scenario_permission", "can_manage_values", schema="osmosys")
    op.drop_column("scenario", "is_template", schema="osmosys")


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Extender permisos de escenarios y habilitar auditoría de catálogos.
#
# Posibles mejoras:
# - Backfill de datos de auditoría inicial para trazabilidad histórica.
#
# Riesgos en producción:
# - Permisos nuevos requieren actualización de lógica de autorización en API/services.
#
# Escalabilidad:
# - Impacto bajo; nueva tabla crece según actividad de catálogos.
