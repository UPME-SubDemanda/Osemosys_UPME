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


def replay(raw: pd.DataFrame, factors: pd.DataFrame, *, mapping=None, assumptions=None) -> pd.DataFrame:
    required = {"scenario", "variable_name", "region", "technology", "year", "value_pj_per_year"}
    if not required.issubset(raw.columns):
        raise ValueError(f"RawResultsLong missing columns: {sorted(required-set(raw.columns))}")
    # Wide exports contain blank placeholders. Keep observed cells only, as in
    # the existing reporter; disclose missing cells instead of filling with zero.
    capacities = raw[raw.variable_name.isin(["NewCapacity", "AccumulatedNewCapacity"])
        & raw.value_pj_per_year.notna() & (raw.year >= 2025)].copy()
    if capacities.duplicated(["scenario", "variable_name", "region", "technology", "year"]).any():
        raise ValueError("Duplicate capacity records would double-count employment")
    mapping = load_technology_mapping() if mapping is None else mapping
    assumptions = load_technology_assumptions(mapping) if assumptions is None else assumptions
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


def compare(old: pd.DataFrame, new: pd.DataFrame, keys: list[str], value: str, *, structural_zeros=False) -> pd.DataFrame:
    merged = old[keys+[value]].merge(new[keys+[value]], on=keys, how="outer", suffixes=("_old", "_new"), validate="one_to_one", indicator="record_presence")
    if structural_zeros:
        # Absent derived rows caused by a changed construction schedule are zero;
        # missing observed capacity cells were already excluded in replay.
        merged.loc[merged.record_presence == "right_only", value+"_old"] = 0.0
        merged.loc[merged.record_presence == "left_only", value+"_new"] = 0.0
    if merged[[value+"_old", value+"_new"]].isna().any().any():
        raise ValueError("Old/new comparison has unmatched keys; investigate before reporting deltas")
    merged["absolute_change"] = merged[value+"_new"] - merged[value+"_old"]
    merged["percentage_change"] = merged["absolute_change"].div(merged[value+"_old"].where(merged[value+"_old"] != 0)) * 100
    return merged



def compare_mappings(old, new, old_mapping, new_mapping):
    """Compare phase coefficients resolved through each version's actual model mapping."""
    lookups = [table.set_index(["Technology", "Factor_Type", "Job_Type", "Year"])
               for table in (old, new)]
    records = []
    for code in ("PWRHYDROR", "PWRHYDROR_NDC", "PWRNUC"):
        components = [mapping[code] for mapping in (old_mapping, new_mapping)]
        if any(len(items) != 1 for items in components):
            raise ValueError(f"Expected a single employment component for {code}")
        before, after = [items[0] for items in components]
        for year in range(2024, 2056):
            for phase in ("Construction", "Manufacturing", "Construction&Manufacturing", "O&M"):
                factors = [lookup.loc[(component.employment_technology, phase, "Direct", year)]
                           for lookup, component in zip(lookups, (before, after))]
                if any(isinstance(factor, pd.DataFrame) for factor in factors):
                    raise ValueError("Ambiguous mapped employment coefficients")
                if factors[0]["Unit"] != factors[1]["Unit"]:
                    raise ValueError("Mapped coefficient units differ")
                values = [float(factor["Value_Numeric"]) * component.multiplier
                          for factor, component in zip(factors, (before, after))]
                records.append({"technology": code, "year": year, "phase": phase,
                    "unit": factors[0]["Unit"],
                    "employment_technology_old": before.employment_technology,
                    "employment_technology_new": after.employment_technology,
                    "source_old": factors[0]["Source"], "source_new": factors[1]["Source"],
                    "value_old": values[0], "value_new": values[1],
                    "absolute_change": values[1] - values[0],
                    "percentage_change": (values[1] / values[0] - 1) * 100 if values[0] else None})
    return pd.DataFrame(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-workbook", type=Path, required=True)
    parser.add_argument("--old-factors", type=Path, required=True)
    parser.add_argument("--new-factors", type=Path, help="Optional scenario model-factor CSV; default is the verified backend snapshot")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--old-mapping", type=Path, help="Preserved pre-change model-code mapping")
    parser.add_argument("--old-assumptions", type=Path, help="Preserved pre-change employment timing")
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
    common = set(old.Technology) & set(new.Technology)
    factor_comparison = compare(old[old.Technology.isin(common)], new[new.Technology.isin(common)], factor_keys, "Value_Numeric")
    old_mapping = load_technology_mapping(args.old_mapping)
    old_assumptions = load_technology_assumptions(old_mapping, args.old_assumptions)
    results = compare(replay(raw, old, mapping=old_mapping, assumptions=old_assumptions), replay(raw, new),
                      ["scenario", "region", "technology", "year", "variable", "unit"], "value", structural_zeros=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    mapping_comparison = compare_mappings(old, new, old_mapping, load_technology_mapping())
    mapping_comparison.to_csv(args.output_dir / "mapping_factor_comparison.csv", index=False, float_format="%.12g", lineterminator="\n")
    additions = new[~new.Technology.isin(set(old.Technology))]
    removals = old[~old.Technology.isin(set(new.Technology))]
    additions.to_csv(args.output_dir / "factor_additions.csv", index=False, lineterminator="\n")
    removals.to_csv(args.output_dir / "factor_removals.csv", index=False, lineterminator="\n")
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
        "conventions": "Unchanged deployment. New-build stock only for annual O&M; commissioning-year factors and uniform construction scheduling. Annual model years; cumulative output is FTE-years. Separate constant SMR conventional-nuclear proxy; SMR employment timing 8/40 years. Structural derived rows introduced by schedule changes are explicitly zero only in the counterpart replay.",
        "old_mapping_sha256": hashlib.sha256(args.old_mapping.read_bytes()).hexdigest() if args.old_mapping else None,
        "old_assumptions_sha256": hashlib.sha256(args.old_assumptions.read_bytes()).hexdigest() if args.old_assumptions else None,
        "added_factor_rows": len(additions), "removed_factor_rows": len(removals),
        "mapping_effect": "Old replay uses supplied baseline mapping/assumptions; new replay uses runtime mapping/assumptions. Changes include factors, hydro classification and Nuclear-to-SMR reassignment."}
    (args.output_dir / "comparison_provenance.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output_dir": str(args.output_dir), "result_rows": len(results), "changed_factor_rows": metadata["changed_factor_rows"]}))


if __name__ == "__main__":
    main()
