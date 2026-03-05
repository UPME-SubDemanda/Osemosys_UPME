"""set default uuid for core.user.id

Revision ID: 20260218_0004
Revises: 20260218_0003
Create Date: 2026-02-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260218_0004"
down_revision = "20260218_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text('ALTER TABLE core."user" ALTER COLUMN id SET DEFAULT gen_random_uuid()'))


def downgrade() -> None:
    op.execute(sa.text('ALTER TABLE core."user" ALTER COLUMN id DROP DEFAULT'))


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Establecer default server-side UUID para nuevas filas de `core.user`.
#
# Posibles mejoras:
# - Verificar extensión `pgcrypto` antes de aplicar en entornos heterogéneos.
#
# Riesgos en producción:
# - Dependencia de `gen_random_uuid()` requiere extensión habilitada.
#
# Escalabilidad:
# - Cambio DDL mínimo.

