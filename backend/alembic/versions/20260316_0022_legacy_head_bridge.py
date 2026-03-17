"""Bridge legacy production Alembic head imported from the monorepo.

This revision is intentionally a no-op. Production databases restored from the
previous stack already carry revision ``20260316_0022``, but the separated
backend repository history currently stops at ``20260306_0021``. Keeping this
bridge revision allows Alembic to recognize that imported databases are at the
current head without forcing an unsafe downgrade or schema rewrite.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260316_0022"
down_revision = "20260306_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Legacy bridge migration."""
    pass


def downgrade() -> None:
    """Legacy bridge migration."""
    pass
