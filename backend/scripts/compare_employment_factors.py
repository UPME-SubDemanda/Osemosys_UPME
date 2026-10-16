"""Replay fixed deployment results with old/new factors; no solver or database."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.services.employment_factors_service import (
    calculate_employment_outputs, employment_factor_provenance,
    load_model_employment_factors, load_technology_assumptions, load_technology_mapping,
)


def replay(raw: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    required = {"scenario", "variable_name", "region", "technology", "year", "value_pj_per_year"}
    if not required.issubset(raw.columns):
        raise ValueError(f"RawResultsLong missing columns: {sorted(required-set(raw.columns))}")
    # Wide exports contain blank placeholders. Keep observed cells only, as in
    # the existing reporter; disclose missing cells instead of filling with zero.
    capacities = raw[raw.variable_name.isin(["NewCapacity", "AccumulatedNewCapacity"])
        & raw.value_pj_per_year.notna() & (raw.year >= 2025)].copy()
    if capacities.duplicated(["scenario", "variable_name", "region", "technology", "year"]).any():
        raise ValueError("Duplicate capacity records would double-count employment")
    mapping = load_technology_mapping()
    assumptions = load_technology_assumptions(mapping)
    regions = {name: i for i, name in enumerate(sorted(capacities.region.unique()), 1)}
    technologies = {name: i for i, name in enumerate(sorted(capacities.technology.unique()), 1)}
    records = []
    for scenario, group in capacities.groupby("scenario"):
        solution = {"new_capacity": [], "intermediate_variables": {"AccumulatedNewCapacity": []},
                    "dimension_lookups": {"REGION": regions, "TECHNOLOGY": technologies}}
        for row in group.itertuples():
            if pd.isna(row.value_pj_per_year):
                raise ValueError("Missing capacity value in fixed baseline")
            if row.variable_name == "NewCapacity":
                solution["new_capacity"].append({"region_id": regions[row.region], "technology_id": technologies[row.technology],
                    "region_name": row.region, "technology_name": row.technology, "year": int(row.year), "new_capacity": row.value_pj_per_year})
            else:
                solution["intermediate_variables"]["AccumulatedNewCapacity"].append({"index": [row.region, row.technology, int(row.year)], "value": row.value_pj_per_year})
        for row in calculate_employment_outputs(solution, factors=factors, mapping=mapping, assumptions=assumptions):
            variable = row["variable_name"]
            records.append({"scenario": scenario, "region": row["region_name"], "technology": row["technology_name"],
                "year": row["year"], "variable": variable, "unit": "FTE-years" if "FTEyear" in variable else "annual FTE", "value": row["value"]})
    return pd.DataFrame(records)


def compare(old: pd.DataFrame, new: pd.DataFrame, keys: list[str], value: str) -> pd.DataFrame:
    merged = old[keys+[value]].merge(new[keys+[value]], on=keys, how="outer", suffixes=("_old", "_new"), validate="one_to_one")
    if merged[[value+"_old", value+"_new"]].isna().any().any():
        raise ValueError("Old/new comparison has unmatched keys; investigate before reporting deltas")
    merged["absolute_change"] = merged[value+"_new"] - merged[value+"_old"]
    merged["percentage_change"] = merged["absolute_change"].div(merged[value+"_old"].where(merged[value+"_old"] != 0)) * 100
    return merged


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-workbook", type=Path, required=True)
    parser.add_argument("--old-factors", type=Path, required=True)
    parser.add_argument("--new-factors", type=Path, help="Optional scenario model-factor CSV; default is the verified backend snapshot")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    raw = pd.read_excel(args.baseline_workbook, sheet_name="RawResultsLong")
    old = pd.read_csv(args.old_factors)
    new = pd.read_csv(args.new_factors) if args.new_factors else load_model_employment_factors()
    scenario_provenance = employment_factor_provenance()
    if args.new_factors:
        scenario_manifest = json.loads((args.new_factors.parent / "employment_factor_provenance.json").read_text(encoding="utf-8"))
        actual_hash = hashlib.sha256(args.new_factors.read_bytes()).hexdigest()
        if scenario_manifest["output_sha256"].get(args.new_factors.name) != actual_hash:
            raise ValueError("Scenario factor checksum does not match its provenance")
        scenario_provenance = {key: scenario_manifest[key] for key in (
            "source_revision", "source_content_sha256", "scenario", "productivity_ratio",
            "employment_multiplier", "productivity_transfer", "solar_transfer_status")}
    factor_keys = ["Technology", "Factor_Type", "Job_Type", "Unit", "Year"]
    factor_comparison = compare(old, new, factor_keys, "Value_Numeric")
    results = compare(replay(raw, old), replay(raw, new), ["scenario", "region", "technology", "year", "variable", "unit"], "value")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    missing = raw[raw.variable_name.isin(["NewCapacity", "AccumulatedNewCapacity"])
        & raw.value_pj_per_year.isna()]
    missing.to_csv(args.output_dir / "unobserved_capacity_cells.csv", index=False, lineterminator="\n")
    factor_comparison.to_csv(args.output_dir / "factor_comparison.csv", index=False, float_format="%.12g", lineterminator="\n")
    results.to_csv(args.output_dir / "employment_comparison.csv", index=False, float_format="%.12g", lineterminator="\n")
    # Only one-off cohort labour is summed here; annual FTE and cumulative rows
    # must not be added across years and then described as annual jobs.
    cohort = results[results.variable == "Employment_FTEyear_ConsManu_Direct"]
    summary = cohort.groupby(["scenario", "unit"])[["value_old", "value_new", "absolute_change"]].sum().reset_index()
    summary.to_csv(args.output_dir / "construction_cohort_totals.csv", index=False, float_format="%.12g", lineterminator="\n")
    ratios = []
    for label, table in [("old", old), ("new", new)]:
        for (phase, category, year), group in table.groupby(["Factor_Type", "Job_Type", "Year"]):
            solar = group.set_index("Technology").Value_Numeric
            if "Rooftop solar PV" in solar and "Utility-scale solar PV" in solar:
                denominator = solar["Utility-scale solar PV"]
                ratios.append({"version": label, "phase": phase, "category": category, "year": year,
                    "rooftop_utility_ratio": solar["Rooftop solar PV"] / denominator if denominator else None})
    pd.DataFrame(ratios).to_csv(args.output_dir / "solar_factor_ratios.csv", index=False, float_format="%.12g", lineterminator="\n")
    metadata = {"baseline_workbook_sha256": hashlib.sha256(args.baseline_workbook.read_bytes()).hexdigest(),
        "old_factors_sha256": hashlib.sha256(args.old_factors.read_bytes()).hexdigest(),
        "new_factors_sha256": hashlib.sha256(args.new_factors.read_bytes()).hexdigest() if args.new_factors else employment_factor_provenance()["factor_table_sha256"],
        "runtime_provenance": employment_factor_provenance(), "raw_rows": len(raw), "result_rows": len(results),
        "factor_scenario_provenance": scenario_provenance,
        "unobserved_capacity_cells": len(missing),
        "missing_data_convention": "Blank exported cells excluded in both replays, matching the existing reporter; not replaced by zero. Completeness of the original solver output cannot be re-established without the original scenario exports.",
        "changed_factor_rows": int((factor_comparison.absolute_change.abs() > 1e-10).sum()),
        "conventions": "Unchanged deployment. New-build stock only for annual O&M; commissioning-year factors and uniform construction scheduling. Annual model years; cumulative output is FTE-years. No separate SMR factor or invented SMR ratio.",
        "mapping_effect": "Both replays use the corrected mapping. Regional mapping coverage is tested separately; this comparison isolates factors."}
    (args.output_dir / "comparison_provenance.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(args.output_dir), "result_rows": len(results), "changed_factor_rows": metadata["changed_factor_rows"]}))


if __name__ == "__main__":
    main()
