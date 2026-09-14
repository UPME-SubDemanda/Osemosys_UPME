"""Add UPSREF to remaining refineria filter groups for regional mode.

Revision ID: 20260914_0046
Revises: 20260914_0045
Create Date: 2026-09-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260914_0046"
down_revision = "20260914_0045"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"

GROUPS_TO_UPDATE = [
    "TECNOLOGIAS_REFINERIAS_IMPORTACIONES",
    "TECNOLOGIAS_REFINERIAS_CARTAGENA",
    "TECNOLOGIAS_REFINERIAS_BAR_CAR",
    "TECNOLOGIAS_REFINERIAS_IMPORTACIONES_LIQUIDOS",
]


def _add_upsref_to_group(bind, group_code: str) -> None:
    group = bind.execute(
        sa.text(
            "SELECT id FROM osemosys.catalog_meta_filter_group WHERE code = :code"
        ),
        {"code": group_code},
    ).fetchone()
    if not group:
        return
    group_id = group[0]

    existing = bind.execute(
        sa.text(
            "SELECT 1 FROM osemosys.catalog_meta_filter_member "
            "WHERE group_id = :gid AND value = 'UPSREF'"
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
            "VALUES (:gid, 'CODE', 'INCLUDE', 'TECHNOLOGY', 'EXACT', 'UPSREF', :sort)"
        ),
        {"gid": group_id, "sort": max_sort + 1},
    )


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "catalog_meta_filter_group" not in insp.get_table_names(schema=SCHEMA):
        return

    for group_code in GROUPS_TO_UPDATE:
        _add_upsref_to_group(bind, group_code)


def downgrade() -> None:
    bind = op.get_bind()

    for group_code in GROUPS_TO_UPDATE:
        group = bind.execute(
            sa.text(
                "SELECT id FROM osemosys.catalog_meta_filter_group WHERE code = :code"
            ),
            {"code": group_code},
        ).fetchone()
        if not group:
            continue
        bind.execute(
            sa.text(
                "DELETE FROM osemosys.catalog_meta_filter_member "
                "WHERE group_id = :gid AND value = 'UPSREF'"
            ),
            {"gid": group[0]},
        )
