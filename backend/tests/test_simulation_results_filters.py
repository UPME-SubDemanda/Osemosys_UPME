from __future__ import annotations

from sqlalchemy.dialects import postgresql

from app.services.simulation_results_service import (
    SimulationResultsService,
)


def _compile_where(clauses: list[object]) -> str:
    dialect = postgresql.dialect()
    return " AND ".join(
        str(clause.compile(dialect=dialect, compile_kwargs={"literal_binds": True}))
        for clause in clauses
    )


def test_single_year_rule_selects_matching_dimension_groups() -> None:
    clauses = SimulationResultsService._year_rules_clauses(
        None,  # type: ignore[arg-type]
        job_id=11,
        year_rules=[(2030, "gt", 0)],
    )

    sql = _compile_where(clauses)

    assert "(osemosys.osemosys_output_param_value.variable_name" in sql
    assert "osemosys.osemosys_output_param_value.id_simulation_job = 11" in sql
    assert "osemosys.osemosys_output_param_value.year = 2030" in sql
    assert "osemosys.osemosys_output_param_value.value > 0" in sql
    assert "SELECT DISTINCT" in sql.upper()
