from __future__ import annotations

import pytest

import app.services.scenario_service as scenario_service_module
from app.core.exceptions import ConflictError, ForbiddenError
from app.models import OsemosysParamValue
from app.services.scenario_service import ScenarioService
from app.services.change_request_service import ChangeRequestService

from factories import create_osemosys_value, create_permission, create_scenario, create_user


def test_change_request_pending_approve_reject_and_history(db_session) -> None:
    owner = create_user(db_session, username="owner-cr")
    proposer = create_user(db_session, username="proposer-cr")

    scenario = create_scenario(
        db_session,
        name="Escenario CR",
        owner=owner.username,
        edit_policy="RESTRICTED",
    )
    create_permission(
        db_session,
        scenario_id=scenario.id,
        user=proposer,
        can_propose=True,
    )
    row = create_osemosys_value(
        db_session,
        scenario_id=scenario.id,
        param_name="CapitalCost",
        year=2025,
        value=10.0,
    )

    pending = ChangeRequestService.create(
        db_session,
        current_user=proposer,
        id_osemosys_param_value=row.id,
        new_value=15.0,
    )
    assert pending["status"] == "PENDING"
    db_session.refresh(row)
    assert row.value == 10.0

    mine = ChangeRequestService.list_my_requests(db_session, current_user=proposer)
    assert [entry["id"] for entry in mine] == [pending["id"]]

    pending_rows = ChangeRequestService.list_pending_by_scenario(
        db_session,
        scenario_id=scenario.id,
        current_user=owner,
    )
    assert [entry["id"] for entry in pending_rows] == [pending["id"]]

    approved = ChangeRequestService.approve(
        db_session,
        current_user=owner,
        change_request_id=pending["id"],
    )
    assert approved["status"] == "APPROVED"
    db_session.refresh(row)
    assert row.value == 15.0

    second = ChangeRequestService.create(
        db_session,
        current_user=proposer,
        id_osemosys_param_value=row.id,
        new_value=18.0,
    )
    rejected = ChangeRequestService.reject(
        db_session,
        current_user=owner,
        change_request_id=second["id"],
    )
    assert rejected["status"] == "REJECTED"
    db_session.refresh(row)
    assert row.value == 15.0

    with pytest.raises(ConflictError):
        ChangeRequestService.approve(
            db_session,
            current_user=owner,
            change_request_id=second["id"],
        )


def test_change_request_owner_only_blocks_non_owner(db_session) -> None:
    owner = create_user(db_session, username="owner-private")
    outsider = create_user(db_session, username="outsider-private")
    scenario = create_scenario(
        db_session,
        name="Privado CR",
        owner=owner.username,
        edit_policy="OWNER_ONLY",
    )
    row = create_osemosys_value(
        db_session,
        scenario_id=scenario.id,
        param_name="Demand",
        year=2025,
        value=5.0,
    )

    with pytest.raises(ForbiddenError):
        ChangeRequestService.create(
            db_session,
            current_user=outsider,
            id_osemosys_param_value=row.id,
            new_value=9.0,
        )


def test_change_request_tracks_changed_param_names_for_child_scenarios(db_session, monkeypatch) -> None:
    monkeypatch.setattr(scenario_service_module, "osemosys_table", lambda table_name: table_name)

    owner = create_user(db_session, username="owner-lineage-cr")
    proposer = create_user(db_session, username="proposer-lineage-cr")

    parent = create_scenario(
        db_session,
        name="Padre CR",
        owner=owner.username,
        edit_policy="OPEN",
    )
    parent_row = create_osemosys_value(
        db_session,
        scenario_id=parent.id,
        param_name="CapitalCost",
        year=2025,
        value=10.0,
    )

    child = ScenarioService.clone(
        db_session,
        source_scenario_id=parent.id,
        current_user=owner,
        name="Hijo CR",
        description=None,
        edit_policy="RESTRICTED",
    )
    create_permission(
        db_session,
        scenario_id=child["id"],
        user=proposer,
        can_propose=True,
    )
    child_row = (
        db_session.query(OsemosysParamValue)
        .filter(
            OsemosysParamValue.id_scenario == child["id"],
            OsemosysParamValue.param_name == parent_row.param_name,
            OsemosysParamValue.year == 2025,
        )
        .one()
    )

    pending = ChangeRequestService.create(
        db_session,
        current_user=proposer,
        id_osemosys_param_value=child_row.id,
        new_value=14.0,
    )
    assert pending["status"] == "PENDING"

    ChangeRequestService.approve(
        db_session,
        current_user=owner,
        change_request_id=pending["id"],
    )

    refreshed_child = ScenarioService.get_public(
        db_session,
        scenario_id=child["id"],
        current_user=owner,
    )
    assert refreshed_child["changed_param_names"] == ["CapitalCost"]
