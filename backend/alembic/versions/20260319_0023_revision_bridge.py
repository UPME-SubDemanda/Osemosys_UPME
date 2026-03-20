"""revision bridge for production databases stamped to 20260319_0023

Revision ID: 20260319_0023
Revises: 20260317_0023
Create Date: 2026-03-20 04:40:00.000000
"""

from typing import Sequence, Union


revision: str = "20260319_0023"
down_revision: Union[str, Sequence[str], None] = "20260317_0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Bridge revision kept intentionally empty.

    Some production databases were stamped with this Alembic revision during the
    earlier public-backend rollout history. The current rewritten history does
    not require additional schema changes at this point, but the revision must
    continue to exist so `alembic upgrade head` can resolve the database state.
    """


def downgrade() -> None:
    """No-op downgrade for bridge revision."""

