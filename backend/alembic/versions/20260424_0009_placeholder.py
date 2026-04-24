"""Placeholder / no-op.

Incorpora ``20260424_0009`` en la cadena sin requerir ``20260424_0008`` (el puente
0008 no se versionó en main; ``head`` sigue 0007 → 0009). Si en algún entorno
quedó ``alembic_version = 20260424_0009`` por pruebas, el grafo queda resoluble.

No aplica ningún cambio de esquema.

Revision ID: 20260424_0009
Revises: 20260424_0007
Create Date: 2026-04-24
"""

from __future__ import annotations

revision = "20260424_0009"
down_revision = "20260424_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op."""


def downgrade() -> None:
    """No-op."""
