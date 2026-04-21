"""merge develop (display_name / simulation_type) with run_iis_analysis

Revision ID: 20260421_0029
Revises: 20260418_0030, 20260421_0028
Create Date: 2026-04-21

Merge-only migration: une las cabeceras ``20260418_0030`` (convergencia de
develop: display_name, simulation_type, parallel_weight, scenario processing
mode) y ``20260421_0028`` (feature de diagnóstico on-demand: ``run_iis_analysis``)
en un único head ``20260421_0029``. No ejecuta DDL: Alembic ya aplicó cada
rama por separado.
"""

from __future__ import annotations


revision = "20260421_0029"
down_revision = ("20260418_0030", "20260421_0028")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
