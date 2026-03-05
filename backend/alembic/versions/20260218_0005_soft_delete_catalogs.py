"""add is_active soft delete columns to catalogs

Revision ID: 20260218_0005
Revises: 20260218_0004
Create Date: 2026-02-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260218_0005"
down_revision = "20260218_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "parameter",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        schema="osmosys",
    )
    op.add_column(
        "region",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        schema="osmosys",
    )
    op.add_column(
        "technology",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        schema="osmosys",
    )
    op.add_column(
        "fuel",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        schema="osmosys",
    )
    op.add_column(
        "emission",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        schema="osmosys",
    )
    op.add_column(
        "solver",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        schema="osmosys",
    )


def downgrade() -> None:
    op.drop_column("solver", "is_active", schema="osmosys")
    op.drop_column("emission", "is_active", schema="osmosys")
    op.drop_column("fuel", "is_active", schema="osmosys")
    op.drop_column("technology", "is_active", schema="osmosys")
    op.drop_column("region", "is_active", schema="osmosys")
    op.drop_column("parameter", "is_active", schema="osmosys")


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Incorporar soft delete en catálogos críticos.
#
# Posibles mejoras:
# - Añadir índices parciales por `is_active` para consultas frecuentes.
#
# Riesgos en producción:
# - Endpoints deben filtrar correctamente para evitar exposición de inactivos.
#
# Escalabilidad:
# - DDL simple; impacto bajo.
