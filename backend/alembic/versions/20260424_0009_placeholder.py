"""Placeholder / no-op.

Se creó este archivo vacío porque la BD de algún entorno quedó registrada en
``alembic_version = 20260424_0009`` (probablemente una migración experimental
que luego se descartó). Sin este archivo, ``alembic upgrade head`` falla con
"Can't locate revision identified by '20260424_0009'".

No aplica ningún cambio de schema — sólo reconcilia el puntero de revisiones.

Revision ID: 20260424_0009
Revises: 20260424_0008
Create Date: 2026-04-24
"""

from __future__ import annotations

revision = "20260424_0009"
down_revision = "20260424_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op."""


def downgrade() -> None:
    """No-op."""
