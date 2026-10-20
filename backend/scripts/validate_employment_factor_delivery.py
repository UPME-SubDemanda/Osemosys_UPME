"""Validate source/output hashes, reproducibility and scenario ordering read-only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

NAMES = ("employment_factors_with_2030_2050.csv", "employment_factors_yearly_2024_2055.csv",
         "employment_factors_model_default_2024_2055.csv", "technology_assumptions_2024.csv")


def validate(root: Path, rebuild: Path | None = None) -> dict:
    processed = root / "data/processed"
    manifest = json.loads((processed / "employment_factor_provenance.json").read_text(encoding="utf-8"))
    for name in NAMES:
        data = (processed / name).read_bytes()
        if data != (root / "src/colombia_employment_factors/data" / name).read_bytes():
            raise ValueError(f"Packaged/generated CSV mismatch: {name}")
        if rebuild and data != (rebuild / name).read_bytes():
            raise ValueError(f"Non-reproducible CSV: {name}")
    for name, expected in manifest["input_sha256"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Stale input provenance: {name}")
    for name, expected in manifest["output_sha256"].items():
        if hashlib.sha256((processed / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Output checksum mismatch: {name}")
    keys = ["Technology", "Factor_Type", "Job_Type", "Unit", "Year"]
    cases = {}
    for case, directory in [("low", "scenarios/low-catalogue-selective"), ("central", "."), ("high", "scenarios/high-catalogue-selective")]:
        table = pd.read_csv(processed / directory / NAMES[2])
        if table.duplicated(keys).any() or table.Value_Numeric.isna().any():
            raise ValueError(f"Invalid scenario keys/numbers: {case}")
        cases[case] = table.set_index(keys).Value_Numeric.sort_index()
    if not cases["low"].index.equals(cases["central"].index) or not cases["central"].index.equals(cases["high"].index):
        raise ValueError("Scenario factor keys differ")
    if not ((cases["low"] - cases["central"]) <= 1e-10).all() or not ((cases["central"] - cases["high"]) <= 1e-10).all():
        raise ValueError("Low/central/high factor ordering failed")
    baseline = pd.read_csv(root / "data/audit/baseline_model_default_23b7f592.csv").set_index(keys).Value_Numeric.sort_index()
    unchanged = ["Nuclear"] + ([] if manifest["solar_transfer_ready"] else ["Rooftop solar PV"])
    for technology in unchanged:
        if not baseline.xs(technology).equals(cases["central"].xs(technology)):
            raise ValueError(f"Unexpected factor change: {technology}")
    return {"packaged_csv_files_identical": 4, "reproducible_csv_files": 4 if rebuild else None,
            "source_and_output_checksums_passed": True, "scenario_ordering_passed": True,
            "unchanged_technologies": unchanged, "source_content_sha256": manifest["source_content_sha256"],
            "solar_transfer_status": manifest["solar_transfer_status"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", type=Path, required=True)
    parser.add_argument("--rebuild-dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(args.source_repo, args.rebuild_dir)))


if __name__ == "__main__":
    main()
