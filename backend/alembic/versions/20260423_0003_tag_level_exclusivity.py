"""Exclusividad combinatoria a nivel de tag (no solo de categoría).

Revision ID: 20260423_0003
Revises: 20260423_0002
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260423_0003"
down_revision = "20260423_0002"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    # Nueva columna en scenario_tag, nullable mientras hacemos backfill
    op.add_column(
        "scenario_tag",
        sa.Column("is_exclusive_combination", sa.Boolean(), nullable=True),
        schema=SCHEMA,
    )

    # Backfill: heredar el flag de la categoría
    conn = op.get_bind()
    conn.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA}.scenario_tag AS t
            SET is_exclusive_combination = c.is_exclusive_combination
            FROM {SCHEMA}.scenario_tag_category AS c
            WHERE c.id = t.category_id
            """
        )
    )

    # Por si algún tag quedó sin categoría (no debería ocurrir con FK RESTRICT)
    conn.execute(
        sa.text(
            f"UPDATE {SCHEMA}.scenario_tag SET is_exclusive_combination = FALSE "
            "WHERE is_exclusive_combination IS NULL"
        )
    )

    op.alter_column(
        "scenario_tag",
        "is_exclusive_combination",
        nullable=False,
        server_default=sa.false(),
        schema=SCHEMA,
    )

    # Ajuste de seed: con exclusividad a nivel tag, sólo "Oficial" es único.
    # "Trabajando" y "Entregado" pierden el flag (heredado del category flag).
    conn.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA}.scenario_tag
            SET is_exclusive_combination = FALSE
            WHERE name IN ('Trabajando', 'Entregado')
              AND category_id = (
                  SELECT id FROM {SCHEMA}.scenario_tag_category WHERE name = 'Estado'
              )
            """
        )
    )
    conn.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA}.scenario_tag
            SET is_exclusive_combination = TRUE
            WHERE name = 'Oficial'
              AND category_id = (
                  SELECT id FROM {SCHEMA}.scenario_tag_category WHERE name = 'Estado'
              )
            """
        )
    )


def downgrade() -> None:
    op.drop_column("scenario_tag", "is_exclusive_combination", schema=SCHEMA)
