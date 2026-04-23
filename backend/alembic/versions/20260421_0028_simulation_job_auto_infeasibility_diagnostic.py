"""simulation_job.run_iis_analysis (auto-run infeasibility diagnostic)

Revision ID: 20260421_0028
Revises: 20260413_0027
Create Date: 2026-04-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260421_0028"
down_revision = "20260413_0027"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    """Añade la columna booleana ``run_iis_analysis`` a ``simulation_job``.

    Cuando es ``true`` y el solver termina infactible, el pipeline corre
    automáticamente el análisis enriquecido (IIS + mapeo a parámetros) en
    lugar de dejarlo para una tarea on-demand. Por defecto ``false``: el
    usuario opta explícitamente en el formulario de encolamiento.
    """
    op.add_column(
        "simulation_job",
        sa.Column(
            "run_iis_analysis",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("simulation_job", "run_iis_analysis", schema=SCHEMA)
