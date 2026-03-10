from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook

import app.services.scenario_service as scenario_service_module
from app.models import OsemosysParamValue
from app.services.official_import_service import OfficialImportService
from app.services.scenario_service import ScenarioService

from factories import (
    create_osemosys_value,
    create_permission,
    create_region,
    create_scenario,
    create_user,
)


def _build_small_excel(*, region_name: str, param_name: str, year: int, value: float) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Parameters"
    sheet.append(["Parameter", "Region", year])
    sheet.append([param_name, region_name, value])
    data = BytesIO()
    workbook.save(data)
    return data.getvalue()


def test_scenario_visibility_metadata_and_changed_params(db_session, monkeypatch) -> None:
    monkeypatch.setattr(scenario_service_module, "osemosys_table", lambda table_name: table_name)

    owner = create_user(db_session, username="owner")
    viewer = create_user(db_session, username="viewer")

    owner_only = create_scenario(
        db_session, name="Privado", owner=owner.username, edit_policy="OWNER_ONLY"
    )
    open_scenario = create_scenario(
        db_session, name="Abierto", owner=owner.username, edit_policy="OPEN"
    )
    restricted = create_scenario(
        db_session, name="Restringido", owner=owner.username, edit_policy="RESTRICTED"
    )
    create_permission(
        db_session,
        scenario_id=restricted.id,
        user=viewer,
        can_edit_direct=True,
        can_manage_values=True,
    )

    listed = ScenarioService.list(
        db_session,
        current_user=viewer,
        busqueda=None,
        owner=None,
        edit_policy=None,
        permission_scope=None,
        cantidad=50,
        offset=1,
    )

    listed_names = {row["name"] for row in listed["data"]}
    assert "Abierto" in listed_names
    assert "Restringido" in listed_names
    assert "Privado" not in listed_names

    restricted_public = ScenarioService.get_public(
        db_session, scenario_id=restricted.id, current_user=viewer
    )
    assert restricted_public["effective_access"]["can_view"] is True
    assert restricted_public["effective_access"]["can_edit_direct"] is True

    updated = ScenarioService.update_metadata(
        db_session,
        scenario_id=restricted.id,
        current_user=viewer,
        payload={"name": "Restringido editado", "description": "Nueva descripción"},
    )
    assert updated["name"] == "Restringido editado"
    assert updated["description"] == "Nueva descripción"

    parent = create_scenario(
        db_session, name="Padre", owner=owner.username, edit_policy="RESTRICTED"
    )
    create_permission(
        db_session,
        scenario_id=parent.id,
        user=viewer,
        can_edit_direct=True,
        can_manage_values=True,
    )
    region = create_region(db_session, name="Norte")
    base_row = create_osemosys_value(
        db_session,
        scenario_id=parent.id,
        param_name="CapitalCost",
        id_region=region.id,
        year=2025,
        value=10.0,
    )

    child = ScenarioService.clone(
        db_session,
        source_scenario_id=parent.id,
        current_user=viewer,
        name="Hijo",
        description="Copia",
        edit_policy="OWNER_ONLY",
    )
    assert child["base_scenario_id"] == parent.id
    assert child["base_scenario_name"] == parent.name
    assert child["changed_param_names"] == []

    cloned_row = (
        db_session.query(OsemosysParamValue)
        .filter(
            OsemosysParamValue.id_scenario == child["id"],
            OsemosysParamValue.param_name == "CapitalCost",
            OsemosysParamValue.id_region == region.id,
            OsemosysParamValue.year == 2025,
        )
        .one()
    )
    updated_child_row = ScenarioService.update_osemosys_value(
        db_session,
        scenario_id=child["id"],
        value_id=cloned_row.id,
        current_user=viewer,
        payload={
            "param_name": "CapitalCost",
            "region_name": region.name,
            "year": 2025,
            "value": 20.0,
        },
    )
    assert updated_child_row["value"] == 20.0

    created_child_row = ScenarioService.create_osemosys_value(
        db_session,
        scenario_id=parent.id,
        current_user=owner,
        payload={
            "param_name": "Demand",
            "region_name": region.name,
            "year": 2025,
            "value": 7.0,
        },
    )
    assert created_child_row["param_name"] == "Demand"

    created_lineage_row = ScenarioService.create_osemosys_value(
        db_session,
        scenario_id=child["id"],
        current_user=viewer,
        payload={
            "param_name": "ResidualCapacity",
            "region_name": region.name,
            "year": 2025,
            "value": 5.0,
        },
    )
    assert created_lineage_row["param_name"] == "ResidualCapacity"
    ScenarioService.deactivate_osemosys_value(
        db_session,
        scenario_id=child["id"],
        value_id=created_lineage_row["id"],
        current_user=viewer,
    )

    child_public = ScenarioService.get_public(
        db_session, scenario_id=child["id"], current_user=viewer
    )
    assert child_public["changed_param_names"] == ["CapitalCost", "ResidualCapacity"]
    assert base_row.id != cloned_row.id


def test_excel_preview_apply_and_update_change_values(db_session) -> None:
    owner = create_user(db_session, username="excel-owner")
    scenario = create_scenario(
        db_session, name="Excel pequeño", owner=owner.username, edit_policy="OWNER_ONLY"
    )
    region = create_region(db_session, name="Centro")
    seeded_row = create_osemosys_value(
        db_session,
        scenario_id=scenario.id,
        param_name="CapitalCost",
        id_region=region.id,
        year=2025,
        value=11.0,
    )

    workbook_v1 = _build_small_excel(
        region_name=region.name,
        param_name="CapitalCost",
        year=2025,
        value=12.5,
    )
    preview = OfficialImportService.preview_scenario_from_excel(
        db_session,
        scenario_id=scenario.id,
        filename="small.xlsx",
        content=workbook_v1,
        selected_sheet_name="Parameters",
    )
    assert preview["total_rows_read"] == 1
    assert preview["not_found"] == 0
    assert len(preview["changes"]) == 1
    assert preview["changes"][0]["row_id"] == seeded_row.id
    assert preview["changes"][0]["old_value"] == 11.0
    assert preview["changes"][0]["new_value"] == 12.5

    applied = OfficialImportService.apply_excel_changes(
        db_session,
        scenario_id=scenario.id,
        changes=preview["changes"],
    )
    assert applied == {"updated": 1, "skipped": 0}
    db_session.refresh(seeded_row)
    assert seeded_row.value == 12.5

    workbook_v2 = _build_small_excel(
        region_name=region.name,
        param_name="CapitalCost",
        year=2025,
        value=14.0,
    )
    updated = OfficialImportService.update_scenario_from_excel(
        db_session,
        scenario_id=scenario.id,
        filename="small.xlsx",
        content=workbook_v2,
        selected_sheet_name="Parameters",
    )
    assert updated["updated"] == 1
    assert updated["not_found"] == 0
    db_session.refresh(seeded_row)
    assert seeded_row.value == 14.0
