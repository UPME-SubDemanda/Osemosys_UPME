from __future__ import annotations

from pathlib import Path

from app.services.csv_scenario_import_service import find_csv_root, validate_csv_root


def _write_csv(root: Path, name: str, rows: list[str] | None = None) -> None:
    content_rows = rows if rows is not None else ["VALUE", "dummy"]
    (root / name).write_text("\n".join(content_rows) + "\n", encoding="utf-8")


def test_find_csv_root_finds_nested_standard_dir(tmp_path: Path) -> None:
    nested = tmp_path / "upload" / "modelo"
    nested.mkdir(parents=True)
    for filename in (
        "YEAR.csv",
        "REGION.csv",
        "TECHNOLOGY.csv",
        "TIMESLICE.csv",
        "MODE_OF_OPERATION.csv",
    ):
        _write_csv(nested, filename)

    found = find_csv_root(tmp_path)

    assert found == nested


def test_validate_csv_root_reports_useful_missing_requirements(tmp_path: Path) -> None:
    for filename in ("YEAR.csv", "REGION.csv", "TECHNOLOGY.csv"):
        _write_csv(tmp_path, filename)

    errors = validate_csv_root(tmp_path)

    assert any("TIMESLICE.csv" in error for error in errors)
    assert any("MODE_OF_OPERATION.csv" in error for error in errors)
    assert any("SpecifiedAnnualDemand.csv" in error for error in errors)
    assert any("OutputActivityRatio.csv" in error for error in errors)


def test_validate_csv_root_accepts_minimal_practical_package(tmp_path: Path) -> None:
    for filename in (
        "YEAR.csv",
        "REGION.csv",
        "TECHNOLOGY.csv",
        "TIMESLICE.csv",
        "MODE_OF_OPERATION.csv",
    ):
        _write_csv(tmp_path, filename)
    _write_csv(tmp_path, "SpecifiedAnnualDemand.csv", ["REGION,FUEL,YEAR,VALUE", "R1,F1,2025,100"])
    _write_csv(
        tmp_path,
        "OutputActivityRatio.csv",
        ["REGION,TECHNOLOGY,FUEL,MODE_OF_OPERATION,YEAR,VALUE", "R1,T1,F1,1,2025,1"],
    )

    errors = validate_csv_root(tmp_path)

    assert errors == []
