"""core user UUID + document catalog

Revision ID: 20260218_0003
Revises: 20260218_0002
Create Date: 2026-02-18

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260218_0003"
down_revision = "20260218_0002"
branch_labels = None
depends_on = None

CORE_SCHEMA = "core"
OSMOSYS_SCHEMA = "osmosys"


def upgrade() -> None:
    # UUID generator (Postgres)
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

    # Catálogo de tipos de documento
    op.create_table(
        "document_type",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("code", name="document_type_code"),
        sa.UniqueConstraint("name", name="document_type_name"),
        schema=CORE_SCHEMA,
    )

    # Tabla nueva de usuario con UUID PK y campos de documento
    op.create_table(
        "user_new",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("username", sa.String(length=150), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("document_number", sa.String(length=50), nullable=True),
        sa.Column("document_type_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_type_id"],
            [f"{CORE_SCHEMA}.document_type.id"],
            ondelete="RESTRICT",
            name="user_new_document_type_id_fkey",
        ),
        sa.UniqueConstraint("email", name="user_new_email"),
        sa.UniqueConstraint("username", name="user_new_username"),
        sa.UniqueConstraint("document_number", name="user_new_document_number"),
        schema=CORE_SCHEMA,
    )

    # Copia datos del user anterior (int) a UUID generados.
    # Guardamos mapeo temporal en una tabla auxiliar para actualizar FKs.
    op.execute(
        sa.text(
            f"""
            CREATE TEMP TABLE tmp_user_id_map(old_id int, new_id uuid);
            INSERT INTO tmp_user_id_map(old_id, new_id)
            SELECT id, gen_random_uuid() FROM {CORE_SCHEMA}."user";

            INSERT INTO {CORE_SCHEMA}.user_new
              (id, email, username, hashed_password, is_active, created_at)
            SELECT m.new_id, u.email, u.username, u.hashed_password, u.is_active, u.created_at
            FROM {CORE_SCHEMA}."user" u
            JOIN tmp_user_id_map m ON m.old_id = u.id;
            """
        )
    )

    # Cambiar FK en scenario_permission: int -> uuid
    op.drop_constraint(
        "scenario_permission_user_id_fkey",
        "scenario_permission",
        schema=OSMOSYS_SCHEMA,
        type_="foreignkey",
    )
    op.drop_index("ix_scenario_permission_user_id", table_name="scenario_permission", schema=OSMOSYS_SCHEMA)

    op.add_column(
        "scenario_permission",
        sa.Column("user_id_uuid", postgresql.UUID(as_uuid=True), nullable=True),
        schema=OSMOSYS_SCHEMA,
    )
    op.execute(
        sa.text(
            f"""
            UPDATE {OSMOSYS_SCHEMA}.scenario_permission sp
            SET user_id_uuid = m.new_id
            FROM tmp_user_id_map m
            WHERE sp.user_id = m.old_id;
            """
        )
    )

    op.drop_column("scenario_permission", "user_id", schema=OSMOSYS_SCHEMA)
    op.alter_column(
        "scenario_permission",
        "user_id_uuid",
        new_column_name="user_id",
        schema=OSMOSYS_SCHEMA,
    )
    op.create_index(
        "ix_scenario_permission_user_id",
        "scenario_permission",
        ["user_id"],
        schema=OSMOSYS_SCHEMA,
    )
    op.create_foreign_key(
        "scenario_permission_user_id_fkey",
        "scenario_permission",
        "user_new",
        ["user_id"],
        ["id"],
        ondelete="RESTRICT",
        source_schema=OSMOSYS_SCHEMA,
        referent_schema=CORE_SCHEMA,
    )

    # Reemplazar tabla user
    op.drop_table("user", schema=CORE_SCHEMA)
    op.rename_table("user_new", "user", schema=CORE_SCHEMA)
    op.execute(sa.text(f'ALTER TABLE {CORE_SCHEMA}."user" RENAME CONSTRAINT user_new_email TO user_email'))
    op.execute(sa.text(f'ALTER TABLE {CORE_SCHEMA}."user" RENAME CONSTRAINT user_new_username TO user_username'))
    op.execute(
        sa.text(
            f'ALTER TABLE {CORE_SCHEMA}."user" RENAME CONSTRAINT user_new_document_number TO user_document_number'
        )
    )

    # Re-apuntar FK al nombre final core.user
    op.drop_constraint(
        "scenario_permission_user_id_fkey",
        "scenario_permission",
        schema=OSMOSYS_SCHEMA,
        type_="foreignkey",
    )
    op.create_foreign_key(
        "scenario_permission_user_id_fkey",
        "scenario_permission",
        "user",
        ["user_id"],
        ["id"],
        ondelete="RESTRICT",
        source_schema=OSMOSYS_SCHEMA,
        referent_schema=CORE_SCHEMA,
    )


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade no soportado para migración de PK int->uuid. "
        "Restaura desde backup si necesitas revertir."
    )


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Migrar PK de `core.user` a UUID y agregar catálogo documental.
#
# Posibles mejoras:
# - Estrategia reversible con tablas sombra y flags de conmutación.
#
# Riesgos en producción:
# - Migración no reversible automáticamente; requiere backup previo obligatorio.
#
# Escalabilidad:
# - Operación sensible por transformación de PK y actualización de FK relacionadas.

