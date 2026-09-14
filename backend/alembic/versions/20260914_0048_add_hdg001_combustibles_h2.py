"""Add HDG001 to COMBUSTIBLES_H2 fuel group for regional H2 compatibility.

The regional model produces H2 fuel with version-suffixed names (HDG001)
that don't match the national naming (HDG). Adding HDG001 enables the
cap_h2 and h2_consumo charts to match in regional mode.

Revision ID: 20260914_0048
Revises: 20260914_0047
Create Date: 2026-09-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260914_0048"
down_revision = "20260914_0047"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "catalog_meta_filter_group" not in insp.get_table_names(schema=SCHEMA):
        return

    group = bind.execute(
        sa.text(
            "SELECT id FROM osemosys.catalog_meta_filter_group WHERE code = :code"
        ),
        {"code": "COMBUSTIBLES_H2"},
    ).fetchone()
    if not group:
        return
    group_id = group[0]

    existing = bind.execute(
        sa.text(
            "SELECT 1 FROM osemosys.catalog_meta_filter_member "
            "WHERE group_id = :gid AND value = 'HDG001'"
        ),
        {"gid": group_id},
    ).fetchone()
    if existing:
        return

    max_sort = bind.execute(
        sa.text(
            "SELECT COALESCE(MAX(sort_order), 0) "
            "FROM osemosys.catalog_meta_filter_member WHERE group_id = :gid"
        ),
        {"gid": group_id},
    ).fetchone()[0]

    bind.execute(
        sa.text(
            "INSERT INTO osemosys.catalog_meta_filter_member "
            "(group_id, member_kind, operation, entity_type, match_mode, value, sort_order) "
            "VALUES (:gid, 'CODE', 'INCLUDE', 'FUEL', 'EXACT', 'HDG001', :sort)"
        ),
        {"gid": group_id, "sort": max_sort + 1},
    )


def downgrade() -> None:
    bind = op.get_bind()

    group = bind.execute(
        sa.text(
            "SELECT id FROM osemosys.catalog_meta_filter_group WHERE code = :code"
        ),
        {"code": "COMBUSTIBLES_H2"},
    ).fetchone()
    if not group:
        return

    bind.execute(
        sa.text(
            "DELETE FROM osemosys.catalog_meta_filter_member "
            "WHERE group_id = :gid AND value = 'HDG001'"
        ),
        {"gid": group[0]},
    )
