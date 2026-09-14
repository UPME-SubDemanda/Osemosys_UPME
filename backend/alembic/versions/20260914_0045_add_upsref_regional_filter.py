"""Add UPSREF to TECNOLOGIAS_REFINERIAS for regional mode support.

Revision ID: 20260914_0044
Revises: 20260606_0043
Create Date: 2026-09-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260914_0045"
down_revision = "20260902_0044"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "catalog_meta_filter_group" not in insp.get_table_names(schema=SCHEMA):
        return

    # Find TECNOLOGIAS_REFINERIAS group
    group = bind.execute(
        sa.text(
            "SELECT id FROM osemosys.catalog_meta_filter_group "
            "WHERE code = 'TECNOLOGIAS_REFINERIAS'"
        )
    ).fetchone()
    if not group:
        return
    group_id = group[0]

    # Check if UPSREF already exists
    existing = bind.execute(
        sa.text(
            "SELECT 1 FROM osemosys.catalog_meta_filter_member "
            "WHERE group_id = :gid AND value = 'UPSREF'"
        ),
        {"gid": group_id},
    ).fetchone()
    if existing:
        return

    # Get max sort_order
    max_sort = bind.execute(
        sa.text(
            "SELECT COALESCE(MAX(sort_order), 0) "
            "FROM osemosys.catalog_meta_filter_member "
            "WHERE group_id = :gid"
        ),
        {"gid": group_id},
    ).fetchone()[0]

    # Insert UPSREF member
    bind.execute(
        sa.text(
            "INSERT INTO osemosys.catalog_meta_filter_member "
            "(group_id, member_kind, operation, entity_type, match_mode, value, sort_order) "
            "VALUES (:gid, 'CODE', 'INCLUDE', 'TECHNOLOGY', 'EXACT', 'UPSREF', :sort)"
        ),
        {"gid": group_id, "sort": max_sort + 1},
    )


def downgrade() -> None:
    bind = op.get_bind()

    group = bind.execute(
        sa.text(
            "SELECT id FROM osemosys.catalog_meta_filter_group "
            "WHERE code = 'TECNOLOGIAS_REFINERIAS'"
        )
    ).fetchone()
    if not group:
        return

    bind.execute(
        sa.text(
            "DELETE FROM osemosys.catalog_meta_filter_member "
            "WHERE group_id = :gid AND value = 'UPSREF'"
        ),
        {"gid": group[0]},
    )
