from __future__ import annotations

from sqlalchemy.dialects import postgresql

from app.services.scenario_service import ScenarioService


def _compile_where(clauses: list[object]) -> str:
    dialect = postgresql.dialect()
    return " AND ".join(
        str(clause.compile(dialect=dialect, compile_kwargs={"literal_binds": True}))
        for clause in clauses
    )


def test_single_year_rule_uses_direct_year_and_value_filters() -> None:
    clauses = ScenarioService._year_rules_clauses(
        None,  # type: ignore[arg-type]
        scenario_id=17,
        year_rules=[(2030, "nonzero", None)],
    )

    sql = _compile_where(clauses)

    assert "osemosys.osemosys_param_value.year = 2030" in sql
    assert "osemosys.osemosys_param_value.value != 0" in sql
    assert "SELECT" not in sql.upper()
    assert " IN " not in sql.upper()
