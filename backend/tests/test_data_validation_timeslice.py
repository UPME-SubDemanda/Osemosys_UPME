from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.simulation.core.data_validation import (
    DataQualityReport,
    detect_demand_profile_not_normalized,
    detect_yearsplit_not_normalized,
    build_report,
)


def _write_csv(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def test_detect_yearsplit_not_normalized_flags_bad_year(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "YearSplit.csv",
        [
            {"TIMESLICE": "1", "YEAR": 2025, "VALUE": 0.6},
            {"TIMESLICE": "2", "YEAR": 2025, "VALUE": 0.3},
            {"TIMESLICE": "1", "YEAR": 2026, "VALUE": 0.5},
            {"TIMESLICE": "2", "YEAR": 2026, "VALUE": 0.5},
        ],
    )

    issues = detect_yearsplit_not_normalized(tmp_path)

    assert len(issues) == 1
    assert issues[0].year == 2025
    assert abs(issues[0].total - 0.9) < 1e-9
    assert abs(issues[0].deviation + 0.1) < 1e-9


def test_detect_yearsplit_not_normalized_accepts_normalized_year(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "YearSplit.csv",
        [
            {"TIMESLICE": "1", "YEAR": 2025, "VALUE": 0.25},
            {"TIMESLICE": "2", "YEAR": 2025, "VALUE": 0.75},
        ],
    )

    assert detect_yearsplit_not_normalized(tmp_path) == []


def test_detect_demand_profile_not_normalized_flags_bad_group(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "SpecifiedDemandProfile.csv",
        [
            {"REGION": "R1", "FUEL": "ELC", "TIMESLICE": "1", "YEAR": 2025, "VALUE": 0.4},
            {"REGION": "R1", "FUEL": "ELC", "TIMESLICE": "2", "YEAR": 2025, "VALUE": 0.4},
            {"REGION": "R1", "FUEL": "GAS", "TIMESLICE": "1", "YEAR": 2025, "VALUE": 1.0},
        ],
    )

    issues = detect_demand_profile_not_normalized(tmp_path)

    assert len(issues) == 1
    assert issues[0].region == "R1"
    assert issues[0].fuel == "ELC"
    assert issues[0].year == 2025
    assert abs(issues[0].total - 0.8) < 1e-9


def test_detect_demand_profile_skips_zero_total(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "SpecifiedDemandProfile.csv",
        [
            {"REGION": "R1", "FUEL": "ELC", "TIMESLICE": "1", "YEAR": 2025, "VALUE": 0.0},
            {"REGION": "R1", "FUEL": "ELC", "TIMESLICE": "2", "YEAR": 2025, "VALUE": 0.0},
        ],
    )

    assert detect_demand_profile_not_normalized(tmp_path) == []


def test_build_report_includes_timeslice_issues(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "YearSplit.csv",
        [{"TIMESLICE": "1", "YEAR": 2025, "VALUE": 0.5}],
    )
    _write_csv(
        tmp_path / "SpecifiedDemandProfile.csv",
        [
            {"REGION": "R1", "FUEL": "ELC", "TIMESLICE": "1", "YEAR": 2025, "VALUE": 0.5},
        ],
    )

    report = build_report(tmp_path, detected_during="csv")

    assert isinstance(report, DataQualityReport)
    assert report.has_warnings()
    assert len(report.yearsplit_issues) == 1
    assert len(report.demand_profile_issues) == 1
    payload = report.to_dict()
    assert payload["summary"]["n_yearsplit_issues"] == 1
    assert payload["summary"]["n_demand_profile_issues"] == 1

    restored = DataQualityReport.from_dict(payload)
    assert restored.yearsplit_issues[0].year == 2025
    assert restored.demand_profile_issues[0].fuel == "ELC"
