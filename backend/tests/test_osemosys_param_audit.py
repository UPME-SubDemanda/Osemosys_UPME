from __future__ import annotations

from app.models import OsemosysParamValueAudit
from app.services.scenario_service import ScenarioService

from factories import create_region, create_scenario, create_user


def test_create_and_update_emit_audit_rows(db_session) -> None:
    owner = create_user(db_session, username="audit_owner")
    scenario = create_scenario(db_session, name="AuditScenario", owner=owner.username)
    create_region(db_session, name="RE1")

    created = ScenarioService.create_osemosys_value(
        db_session,
        scenario_id=scenario.id,
        current_user=owner,
        payload={
            "param_name": "CapitalCost",
            "region_name": "RE1",
            "value": 100.0,
            "year": 2022,
        },
    )
    n_insert = (
        db_session.query(OsemosysParamValueAudit)
        .filter(
            OsemosysParamValueAudit.id_scenario == scenario.id,
            OsemosysParamValueAudit.param_name == "CapitalCost",
            OsemosysParamValueAudit.action == "INSERT",
        )
        .count()
    )
    assert n_insert == 1

    ScenarioService.update_osemosys_value(
        db_session,
        scenario_id=scenario.id,
        value_id=int(created["id"]),
        current_user=owner,
        payload={
            "param_name": "CapitalCost",
            "region_name": "RE1",
            "value": 200.0,
            "year": 2022,
        },
    )
    n_update = (
        db_session.query(OsemosysParamValueAudit)
        .filter(
            OsemosysParamValueAudit.id_scenario == scenario.id,
            OsemosysParamValueAudit.param_name == "CapitalCost",
            OsemosysParamValueAudit.action == "UPDATE",
        )
        .count()
    )
    assert n_update == 1

    page = ScenarioService.list_osemosys_param_audit(
        db_session,
        scenario_id=scenario.id,
        current_user=owner,
        param_name="CapitalCost",
        offset=0,
        limit=10,
    )
    assert page["total"] >= 2
    assert len(page["items"]) >= 1
