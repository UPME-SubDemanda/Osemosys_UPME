"""Categorías jerárquicas de etiquetas y relación M:M escenario↔tag.

Revision ID: 20260423_0002
Revises: 20260423_0001
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260423_0002"
down_revision = "20260423_0001"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    # --- 1) Tabla de categorías ---
    op.create_table(
        "scenario_tag_category",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("hierarchy_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_tags_per_scenario", sa.Integer(), nullable=True, server_default="1"),
        sa.Column(
            "is_exclusive_combination",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("default_color", sa.String(length=7), nullable=False, server_default="#64748B"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_scenario_tag_category_name"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_scenario_tag_category_hierarchy",
        "scenario_tag_category",
        ["hierarchy_level", "sort_order"],
        unique=False,
        schema=SCHEMA,
    )

    # --- 2) Seed: categoría "Escenario" (H2) para migrar tags existentes ---
    conn = op.get_bind()
    escenario_id = conn.execute(
        sa.text(
            f"""
            INSERT INTO {SCHEMA}.scenario_tag_category
                (name, hierarchy_level, sort_order, max_tags_per_scenario,
                 is_exclusive_combination, default_color)
            VALUES ('Escenario', 2, 10, 1, FALSE, '#3B82F6')
            RETURNING id
            """
        )
    ).scalar_one()

    # Categoría "Estado" (H1) con exclusividad combinatoria
    conn.execute(
        sa.text(
            f"""
            INSERT INTO {SCHEMA}.scenario_tag_category
                (name, hierarchy_level, sort_order, max_tags_per_scenario,
                 is_exclusive_combination, default_color)
            VALUES ('Estado', 1, 0, 1, TRUE, '#DC2626')
            """
        )
    )
    estado_id = conn.execute(
        sa.text(
            f"SELECT id FROM {SCHEMA}.scenario_tag_category WHERE name = 'Estado'"
        )
    ).scalar_one()

    # --- 3) Modificar scenario_tag ---
    # Quitar unique name global
    op.drop_constraint("uq_scenario_tag_name", "scenario_tag", schema=SCHEMA, type_="unique")
    # Añadir category_id (nullable temporalmente para backfill)
    op.add_column(
        "scenario_tag",
        sa.Column("category_id", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    # Backfill: todos los tags existentes → categoría "Escenario"
    conn.execute(
        sa.text(
            f"UPDATE {SCHEMA}.scenario_tag SET category_id = :cid WHERE category_id IS NULL"
        ),
        {"cid": escenario_id},
    )
    op.alter_column(
        "scenario_tag",
        "category_id",
        nullable=False,
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_scenario_tag_category_id",
        "scenario_tag",
        "scenario_tag_category",
        ["category_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_scenario_tag_category_id",
        "scenario_tag",
        ["category_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_unique_constraint(
        "uq_scenario_tag_category_tag_name",
        "scenario_tag",
        ["category_id", "name"],
        schema=SCHEMA,
    )

    # --- 4) Seed tags de Estado ---
    conn.execute(
        sa.text(
            f"""
            INSERT INTO {SCHEMA}.scenario_tag (category_id, name, color, sort_order)
            VALUES
                (:cid, 'Trabajando', '#F59E0B', 0),
                (:cid, 'Oficial',    '#EAB308', 10),
                (:cid, 'Entregado',  '#2563EB', 20)
            """
        ),
        {"cid": estado_id},
    )

    # --- 5) Tabla M:M scenario_tag_link ---
    op.create_table(
        "scenario_tag_link",
        sa.Column("scenario_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            [f"{SCHEMA}.scenario.id"],
            ondelete="CASCADE",
            name="fk_scenario_tag_link_scenario",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            [f"{SCHEMA}.scenario_tag.id"],
            ondelete="CASCADE",
            name="fk_scenario_tag_link_tag",
        ),
        sa.PrimaryKeyConstraint("scenario_id", "tag_id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_scenario_tag_link_tag_id",
        "scenario_tag_link",
        ["tag_id"],
        unique=False,
        schema=SCHEMA,
    )

    # --- 6) Migrar scenario.tag_id existente → scenario_tag_link ---
    conn.execute(
        sa.text(
            f"""
            INSERT INTO {SCHEMA}.scenario_tag_link (scenario_id, tag_id)
            SELECT id, tag_id FROM {SCHEMA}.scenario
            WHERE tag_id IS NOT NULL
            ON CONFLICT DO NOTHING
            """
        )
    )

    # --- 7) Eliminar scenario.tag_id ---
    op.drop_constraint(
        "fk_scenario_tag_id_scenario_tag",
        "scenario",
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_index("ix_scenario_tag_id", table_name="scenario", schema=SCHEMA)
    op.drop_column("scenario", "tag_id", schema=SCHEMA)


def downgrade() -> None:
    # Re-crear scenario.tag_id y poblar desde link (primer tag de categoría Escenario)
    op.add_column(
        "scenario",
        sa.Column("tag_id", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index("ix_scenario_tag_id", "scenario", ["tag_id"], unique=False, schema=SCHEMA)
    op.create_foreign_key(
        "fk_scenario_tag_id_scenario_tag",
        "scenario",
        "scenario_tag",
        ["tag_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="SET NULL",
    )
    conn = op.get_bind()
    conn.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA}.scenario s
            SET tag_id = sub.tag_id
            FROM (
                SELECT l.scenario_id, l.tag_id
                FROM {SCHEMA}.scenario_tag_link l
                JOIN {SCHEMA}.scenario_tag t ON t.id = l.tag_id
                JOIN {SCHEMA}.scenario_tag_category c ON c.id = t.category_id
                WHERE c.name = 'Escenario'
            ) sub
            WHERE sub.scenario_id = s.id
            """
        )
    )

    op.drop_index("ix_scenario_tag_link_tag_id", table_name="scenario_tag_link", schema=SCHEMA)
    op.drop_table("scenario_tag_link", schema=SCHEMA)

    # Restaurar unicidad global en scenario_tag.name y quitar category_id
    op.drop_constraint(
        "uq_scenario_tag_category_tag_name",
        "scenario_tag",
        schema=SCHEMA,
        type_="unique",
    )
    op.drop_index("ix_scenario_tag_category_id", table_name="scenario_tag", schema=SCHEMA)
    op.drop_constraint(
        "fk_scenario_tag_category_id",
        "scenario_tag",
        schema=SCHEMA,
        type_="foreignkey",
    )
    # Eliminar tags de Estado antes de soltar category_id (pueden duplicar nombres con Escenario)
    conn.execute(
        sa.text(
            f"""
            DELETE FROM {SCHEMA}.scenario_tag
            WHERE category_id IN (
                SELECT id FROM {SCHEMA}.scenario_tag_category WHERE name = 'Estado'
            )
            """
        )
    )
    op.drop_column("scenario_tag", "category_id", schema=SCHEMA)
    op.create_unique_constraint(
        "uq_scenario_tag_name",
        "scenario_tag",
        ["name"],
        schema=SCHEMA,
    )

    op.drop_index(
        "ix_scenario_tag_category_hierarchy",
        table_name="scenario_tag_category",
        schema=SCHEMA,
    )
    op.drop_table("scenario_tag_category", schema=SCHEMA)
