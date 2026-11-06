"""PCH/SMR integration against the frozen pre-change PR #174 snapshot."""
import json
from importlib import resources
from pathlib import Path

import pandas as pd
import pytest

from app.services.employment_factors_service import (
    calculate_employment_outputs, load_model_employment_factors,
    load_technology_assumptions, load_technology_mapping,
    EMPLOYMENT_FTEYEAR_CONSMANU_DIRECT, EMPLOYMENT_FTE_OM_DIRECT_ANNUAL,
)
from scripts.sync_employment_factor_snapshot import sync

BACKEND = Path(__file__).resolve().parents[1]
BASELINE = BACKEND / "reports/employment_methodology/pch-smr/baseline"
SNAPSHOT = BACKEND / "app/data/employment_factor_snapshot"
MODEL = "employment_factors_model_default_2024_2055.csv"


def baseline_inputs():
    mapping = load_technology_mapping(BASELINE / "employment_factors_mapping.yaml")
    return (pd.read_csv(BASELINE / MODEL), mapping,
            load_technology_assumptions(mapping, BASELINE / "technology_assumptions_2024.csv"))


def one_mw(code, year=2030):
    return {"new_capacity": [{"technology_name": code, "year": year, "new_capacity": .0315576}],
            "intermediate_variables": {"AccumulatedNewCapacity": [{"index": ["RE1", code, year], "value": .0315576}]}}


def test_existing_codes_and_regional_expansion_resolve_to_correct_categories():
    mapping = load_technology_mapping()
    old = load_technology_mapping(BASELINE / "employment_factors_mapping.yaml")
    assert set(mapping) == set(old)  # No duplicate generating technology invented.
    for prefix in ("", "AN_", "CA_", "IN_", "NE_", "OR_", "SE_", "SO_"):
        assert mapping[prefix + "PWRNUC"][0].employment_technology == "SMR"
        assert all(c.employment_technology != "Nuclear" for c in mapping[prefix + "PWRNUC"])
        assert mapping[prefix + "PWRHYDROR"][0].employment_technology == "Hydro (large)"
        assert mapping[prefix + "PWRHYDROR_NDC"][0].employment_technology == "Hydro (small)"


def test_smr_one_mw_uses_proxy_and_2030_smr_timing():
    rows = calculate_employment_outputs(one_mw("PWRNUC"))
    cohort = next(r for r in rows if r["variable_name"] == EMPLOYMENT_FTEYEAR_CONSMANU_DIRECT)
    om = next(r for r in rows if r["variable_name"] == EMPLOYMENT_FTE_OM_DIRECT_ANNUAL)
    assert cohort["value"] == pytest.approx(13.1)
    assert om["value"] == pytest.approx(.6)
    assert cohort["technology_name"] == "PWRNUC"
    from app.services.employment_factors_service import employment_factor_provenance
    assert employment_factor_provenance()["targeted_refresh"]["replacement_productivity_transfer"] == "none"
    component = cohort["components"][0]
    assert component["employment_technology"] == "SMR"
    assert component["source"] == "Rutovitz 2015 (SMR proxy)"
    assert component["construction_time_years"] == 8
    assert component["lifetime_years"] == 40
    assert component["construction_time_source_year"] == component["lifetime_source_year"] == 2030


def test_pch_one_mw_selects_new_source_and_never_sums_separate_manufacturing():
    rows = calculate_employment_outputs(one_mw("PWRHYDROR_NDC", 2025))
    cohort = next(r for r in rows if r["variable_name"] == EMPLOYMENT_FTEYEAR_CONSMANU_DIRECT)
    om = next(r for r in rows if r["variable_name"] == EMPLOYMENT_FTE_OM_DIRECT_ANNUAL)
    assert len(cohort["components"]) == 1
    assert cohort["components"][0]["source"].startswith("ESMAP 2023")
    assert cohort["value"] == pytest.approx(9.66 * (1 + (3.0145922516505728 / 3.02 - 1) / 6))
    assert om["value"] == pytest.approx(.8 * (1 + (66400 / 66500 - 1) / 6))


def test_snapshot_retains_every_unrelated_field_and_all_seven_outputs():
    old = pd.read_csv(BASELINE / MODEL, dtype=str, keep_default_na=False)
    new = pd.read_csv(SNAPSHOT / MODEL, dtype=str, keep_default_na=False)
    unchanged = ~old.Technology.isin(["Hydro (small)", "SMR"])
    keys = ["Technology", "Factor_Type", "Job_Type", "Unit", "Year"]
    pd.testing.assert_frame_equal(
        old[unchanged].sort_values(keys).reset_index(drop=True),
        new[~new.Technology.isin(["Hydro (small)", "SMR"])].sort_values(keys).reset_index(drop=True),
    )
    old_assumptions = pd.read_csv(BASELINE / "technology_assumptions_2024.csv", dtype=str, keep_default_na=False)
    new_assumptions = pd.read_csv(SNAPSHOT / "technology_assumptions_2024.csv", dtype=str, keep_default_na=False)
    pd.testing.assert_frame_equal(old_assumptions, new_assumptions[new_assumptions.Technology != "SMR"].reset_index(drop=True))
    assert len({r["variable_name"] for r in calculate_employment_outputs(one_mw("PWRNUC", 2025))}) == 7


@pytest.mark.parametrize("code", ["PWRWNDONS", "PWRWNDOFS_FIX", "PWRWNDOFS_FLO", "AN_PWRWNDONS"])
def test_wind_outputs_and_metadata_are_identical(code):
    old_factors, old_mapping, old_assumptions = baseline_inputs()
    old = calculate_employment_outputs(one_mw(code, 2035), factors=old_factors, mapping=old_mapping, assumptions=old_assumptions)
    assert calculate_employment_outputs(one_mw(code, 2035)) == old


def test_targeted_sync_is_reproducible_and_rejects_tampering(tmp_path):
    source = Path(str(resources.files("colombia_employment_factors.data")))
    rebuilt = tmp_path / "rebuild"
    sync(source, rebuilt, baseline=BASELINE)
    for name in (MODEL, "technology_assumptions_2024.csv", "employment_factor_provenance.json"):
        assert (rebuilt / name).read_bytes() == (SNAPSHOT / name).read_bytes()
    damaged = tmp_path / "damaged"
    damaged.mkdir()
    for name in (MODEL, "technology_assumptions_2024.csv", "employment_factor_provenance.json"):
        (damaged / name).write_bytes((BASELINE / name).read_bytes())
    (damaged / MODEL).write_text("tampered")
    destination = tmp_path / "must-not-exist"
    with pytest.raises(ValueError, match="checksum"):
        sync(source, destination, baseline=damaged)
    assert not destination.exists()


def test_mapping_comparison_reports_semantic_reassignment_and_effective_values():
    from scripts.compare_employment_factors import compare_mappings
    old, mapping, _ = baseline_inputs()
    table = compare_mappings(old, load_model_employment_factors(), mapping, load_technology_mapping())
    assert len(table) == 3 * 32 * 4
    smr = table[(table.technology == "PWRNUC") & (table.year == 2024) & (table.phase == "Construction&Manufacturing")].iloc[0]
    assert smr.employment_technology_old == "Nuclear"
    assert smr.employment_technology_new == "SMR"
    assert smr.value_old == pytest.approx(20.9)
    assert smr.value_new == pytest.approx(13.1)
    pch = table[(table.technology == "PWRHYDROR_NDC") & (table.year == 2024) & (table.phase == "O&M")].iloc[0]
    assert pch.value_old == pytest.approx(15.955625)
    assert pch.value_new == pytest.approx(.8)
