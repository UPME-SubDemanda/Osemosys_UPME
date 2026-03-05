"""core user schema and permission link

Revision ID: 20260218_0002
Revises: 20260218_0001
Create Date: 2026-02-18

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260218_0002"
down_revision = "20260218_0001"
branch_labels = None
depends_on = None


CORE_SCHEMA = "core"
OSMOSYS_SCHEMA = "osmosys"


def upgrade() -> None:
    op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {CORE_SCHEMA}"))

    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("username", sa.String(length=150), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("email", name="user_email"),
        sa.UniqueConstraint("username", name="user_username"),
        schema=CORE_SCHEMA,
    )

    op.add_column(
        "scenario_permission",
        sa.Column("user_id", sa.Integer(), nullable=True),
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
        "user",
        ["user_id"],
        ["id"],
        ondelete="RESTRICT",
        source_schema=OSMOSYS_SCHEMA,
        referent_schema=CORE_SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint(
        "scenario_permission_user_id_fkey",
        "scenario_permission",
        schema=OSMOSYS_SCHEMA,
        type_="foreignkey",
    )
    op.drop_index("ix_scenario_permission_user_id", table_name="scenario_permission", schema=OSMOSYS_SCHEMA)
    op.drop_column("scenario_permission", "user_id", schema=OSMOSYS_SCHEMA)

    op.drop_table("user", schema=CORE_SCHEMA)
    op.execute(sa.text(f"DROP SCHEMA IF EXISTS {CORE_SCHEMA} CASCADE"))


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Introducir esquema `core.user` y enlace de permisos por FK.
#
# Posibles mejoras:
# - Incluir migración de datos de referencia de usuarios iniciales.
#
# Riesgos en producción:
# - Cambios de FK pueden bloquear si existen datos inconsistentes.
#
# Escalabilidad:
# - Costo moderado, concentrado en DDL y creación de índices.

