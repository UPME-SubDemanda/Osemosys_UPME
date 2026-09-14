"""Add regional crude oil fuel variants to refineria fuel groups.

The regional model uses different fuel naming conventions for crude oils
(e.g. OIL001_1LIV instead of OIL_1LIV). Adding these variants enables
the ref_ambas chart filter to match in regional mode.

Revision ID: 20260914_0047
Revises: 20260914_0046
Create Date: 2026-09-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260914_0047"
down_revision = "20260914_0046"
branch_labels = None
depends_on = None

SCHEMA = "osemosys"

REGIONAL_CRUDE_FUELS = ["OIL001_1LIV", "OIL001_2MED", "OIL001_3PES"]

FUEL_GROUPS_TO_UPDATE = [
    "COMBUSTIBLES_REFINERIA_CON_CRUDO",
    "COMBUSTIBLES_REFINERIA_SIN_CRUDO",
]


def _add_fuel_to_group(bind, group_code: str, fuel: str) -> None:
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
            "WHERE group_id = :gid AND value = :val"
        ),
        {"gid": group_id, "val": fuel},
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
            "VALUES (:gid, 'CODE', 'INCLUDE', 'FUEL', 'EXACT', :val, :sort)"
        ),
        {"gid": group_id, "val": fuel, "sort": max_sort + 1},
    )


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "catalog_meta_filter_group" not in insp.get_table_names(schema=SCHEMA):
        return

    for group_code in FUEL_GROUPS_TO_UPDATE:
        for fuel in REGIONAL_CRUDE_FUELS:
            _add_fuel_to_group(bind, group_code, fuel)


def downgrade() -> None:
    bind = op.get_bind()

    for group_code in FUEL_GROUPS_TO_UPDATE:
        group = bind.execute(
            sa.text(
                "SELECT id FROM osemosys.catalog_meta_filter_group WHERE code = :code"
            ),
            {"code": group_code},
        ).fetchone()
        if not group:
            continue
        for fuel in REGIONAL_CRUDE_FUELS:
            bind.execute(
                sa.text(
                    "DELETE FROM osemosys.catalog_meta_filter_member "
                    "WHERE group_id = :gid AND value = :val"
                ),
                {"gid": group[0], "val": fuel},
            )
