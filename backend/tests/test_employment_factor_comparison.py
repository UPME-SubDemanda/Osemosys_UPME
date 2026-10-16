import pandas as pd
import pytest

from scripts.compare_employment_factors import compare, replay


def test_fixed_deployment_replay_does_not_turn_blank_cells_into_zero_jobs():
    factors = pd.DataFrame([
        {"Technology": "Utility-scale solar PV", "Year": 2025, "Factor_Type": phase,
         "Job_Type": "Direct", "Unit": unit, "Value_Numeric": value, "Source": "fixture"}
        for phase, unit, value in [("Construction&Manufacturing", "job-yr/MW", 6), ("O&M", "job/MW", .2)]
    ])
    raw = pd.DataFrame([
        dict(scenario="fixture", variable_name=var, region="RE1", technology="PWRSOLUGE", year=year, value_pj_per_year=value)
        for var, year, value in [("NewCapacity", 2025, .315576), ("AccumulatedNewCapacity", 2025, .315576), ("AccumulatedNewCapacity", 2026, None)]
    ])
    output = replay(raw, factors)
    assert output.loc[output.variable == "Employment_FTEyear_ConsManu_Direct", "value"].iloc[0] == pytest.approx(60)
    om = output[output.variable == "Employment_FTE_OM_Direct_Annual"]
    assert list(om.year) == [2025]
    assert list(om.value) == pytest.approx([2])


def test_duplicate_baseline_cells_are_rejected():
    raw = pd.DataFrame([dict(scenario="x", variable_name="NewCapacity", region="RE1", technology="PWRSOLUGE", year=2025, value_pj_per_year=1)] * 2)
    with pytest.raises(ValueError, match="Duplicate capacity"):
        replay(raw, pd.DataFrame())


def test_comparison_keeps_zero_baseline_percentage_undefined_and_rejects_unmatched_keys():
    old = pd.DataFrame({"key": ["a"], "value": [0]})
    new = pd.DataFrame({"key": ["a"], "value": [2]})
    result = compare(old, new, ["key"], "value")
    assert result.absolute_change.iloc[0] == 2
    assert pd.isna(result.percentage_change.iloc[0])
    with pytest.raises(ValueError, match="unmatched keys"):
        compare(old, pd.DataFrame({"key": ["b"], "value": [2]}), ["key"], "value")


@pytest.mark.parametrize("failure", ["scenario", "checksum"])
def test_runtime_sync_rejects_unapproved_case_or_tampered_data_before_writing(tmp_path, failure):
    import json
    from scripts.sync_employment_factor_snapshot import FILES, sync
    source = tmp_path / "source"
    source.mkdir()
    manifest = {"scenario": "high" if failure == "scenario" else "central",
                "productivity_transfer": "selective", "solar_projection": "catalogue",
                "output_sha256": {name: "0"*64 for name in FILES}}
    for name in FILES:
        (source / name).write_text("tampered")
    (source / "employment_factor_provenance.json").write_text(json.dumps(manifest))
    destination = tmp_path / "runtime"
    with pytest.raises(ValueError):
        sync(source, destination)
    assert not destination.exists()
