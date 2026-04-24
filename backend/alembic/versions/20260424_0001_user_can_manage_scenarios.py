"""Rol Admin Escenarios: renombra is_admin → can_manage_scenarios con alcance ampliado.

El nuevo flag concede: ver escenarios privados, editar metadatos/política/etiquetas/valores,
administrar permisos granulares, clonar, exportar y eliminar escenarios y simulaciones
ajenas.

Revision ID: 20260424_0001
Revises: 20260423_0004
Create Date: 2026-04-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260424_0001"
down_revision = "20260423_0004"
branch_labels = None
depends_on = None

SCHEMA = "core"


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "can_manage_scenarios",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        schema=SCHEMA,
    )
    # Migrar datos: los que eran is_admin heredan el nuevo flag
    op.execute(
        f'UPDATE {SCHEMA}."user" SET can_manage_scenarios = is_admin WHERE is_admin = TRUE'
    )
    op.drop_column("user", "is_admin", schema=SCHEMA)


def downgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        schema=SCHEMA,
    )
    op.execute(
        f'UPDATE {SCHEMA}."user" SET is_admin = can_manage_scenarios'
    )
    op.drop_column("user", "can_manage_scenarios", schema=SCHEMA)
