"""rename schema osmosys to osemosys

Revision ID: 20260219_0009
Revises: 20260218_0008
Create Date: 2026-02-19

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260219_0009"
down_revision = "20260218_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'osmosys')
                   AND NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'osemosys') THEN
                    EXECUTE 'ALTER SCHEMA osmosys RENAME TO osemosys';
                END IF;
            END
            $$;
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'osemosys')
                   AND NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'osmosys') THEN
                    EXECUTE 'ALTER SCHEMA osemosys RENAME TO osmosys';
                END IF;
            END
            $$;
            """
        )
    )


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Renombrar esquema para alineación semántica (`osmosys` -> `osemosys`).
#
# Posibles mejoras:
# - Validar/actualizar objetos dependientes externos (vistas, grants, ETL).
#
# Riesgos en producción:
# - Integraciones que referencian esquema antiguo pueden fallar tras migración.
#
# Escalabilidad:
# - Cambio DDL puntual, pero con impacto transversal en dependencias.
