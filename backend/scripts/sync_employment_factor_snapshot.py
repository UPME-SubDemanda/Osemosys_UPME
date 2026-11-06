"""Copy verified canonical factors, optionally refreshing only approved PCH/SMR rows."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd

FILES = ("employment_factors_model_default_2024_2055.csv", "technology_assumptions_2024.csv")
DESTINATION = Path(__file__).resolve().parents[1] / "app/data/employment_factor_snapshot"
REFRESH_TECHNOLOGIES = ("Hydro (small)", "SMR")


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verified(directory: Path) -> dict:
    manifest = json.loads((directory / "employment_factor_provenance.json").read_text(encoding="utf-8"))
    for name in FILES:
        if _hash(directory / name) != manifest["output_sha256"][name]:
            raise ValueError(f"Source data checksum mismatch: {name}")
    return manifest


def sync(source: Path, destination: Path = DESTINATION, *, baseline: Path | None = None) -> dict:
    manifest = _verified(source)
    if baseline is None:
        if manifest["scenario"] != "central" or manifest.get("productivity_transfer") != "selective" or manifest["solar_projection"] != "catalogue":
            raise ValueError("Only the approved central/selective/catalogue build may replace the complete runtime snapshot")
        destination.mkdir(parents=True, exist_ok=True)
        for name in (*FILES, "employment_factor_provenance.json"):
            shutil.copyfile(source / name, destination / name)
    else:
        if manifest["scenario"] != "central" or manifest.get("productivity_transfer") != "none" or manifest["solar_projection"] != "catalogue":
            raise ValueError("Targeted refresh requires the canonical central/no-transfer/catalogue build")
        previous = _verified(baseline)
        tables = {}
        for name in FILES:
            old = pd.read_csv(baseline / name, dtype=str, keep_default_na=False)
            new = pd.read_csv(source / name, dtype=str, keep_default_na=False)
            replacement = new[new.Technology.isin(REFRESH_TECHNOLOGIES)]
            if set(replacement.Technology) != set(REFRESH_TECHNOLOGIES):
                raise ValueError(f"Missing approved replacement technologies: {name}")
            keys = ["Technology"]
            if name == FILES[0]:
                keys += ["Factor_Type", "Job_Type", "Unit", "Year"]
                required = {(technology, phase, "Direct", "job/MW" if phase == "O&M" else "job-yr/MW", str(year))
                            for technology in REFRESH_TECHNOLOGIES
                            for phase in ("Construction", "Manufacturing", "Construction&Manufacturing", "O&M")
                            for year in range(2024, 2056)}
                if set(replacement[keys].itertuples(index=False, name=None)) != required:
                    raise ValueError("Incomplete replacement phase/year contract")
            if replacement.duplicated(keys).any():
                raise ValueError(f"Duplicate replacement records: {name}")
            retained = old[~old.Technology.isin(REFRESH_TECHNOLOGIES)]
            table = pd.concat([retained, replacement], ignore_index=True).sort_values(keys).reset_index(drop=True)
            if table.duplicated(keys).any():
                raise ValueError(f"Duplicate integrated records: {name}")
            # Check every field, including source and notes, for all unrelated technologies.
            pd.testing.assert_frame_equal(
                retained.sort_values(keys).reset_index(drop=True),
                table[~table.Technology.isin(REFRESH_TECHNOLOGIES)][old.columns].sort_values(keys).reset_index(drop=True),
            )
            tables[name] = table
        selection = {
            "baseline_manifest_sha256": _hash(baseline / "employment_factor_provenance.json"),
            "baseline_output_sha256": {name: _hash(baseline / name) for name in FILES},
            "baseline_source_revision": previous["source_revision"],
            "replacement_source_revision": manifest["source_revision"],
            "replacement_source_content_sha256": manifest["source_content_sha256"],
            "replacement_output_sha256": {name: _hash(source / name) for name in FILES},
            "replacement_technologies": list(REFRESH_TECHNOLOGIES),
            "replacement_productivity_transfer": "none",
            "convention": "Retain all baseline rows outside Hydro (small)/SMR; mapping changes are separate. Baseline selective productivity and solar choices remain for retained rows.",
        }
        integrated = dict(previous)
        for key in ("source_repository", "source_revision", "source_tree_dirty", "input_sha256"):
            integrated[key] = manifest[key]
        integrated["targeted_refresh"] = selection
        integrated["source_content_sha256"] = hashlib.sha256(json.dumps(selection, sort_keys=True).encode()).hexdigest()
        baseline_sources = pd.read_csv(baseline / FILES[0])[["Technology", "Source"]].drop_duplicates()
        if baseline_sources.Technology.duplicated().any():
            raise ValueError("Multiple baseline default sources for a technology")
        integrated["default_sources"] = dict(zip(baseline_sources.Technology, baseline_sources.Source))
        for technology in REFRESH_TECHNOLOGIES:
            integrated["default_sources"][technology] = manifest["default_sources"][technology]
        destination.mkdir(parents=True, exist_ok=True)
        for name, table in tables.items():
            table.to_csv(destination / name, index=False, lineterminator="\n")
        integrated["output_sha256"] = {name: _hash(destination / name) for name in FILES}
        (destination / "employment_factor_provenance.json").write_text(
            json.dumps(integrated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        manifest = integrated
    return {"destination": str(destination), "source_revision": manifest["source_revision"],
            "source_content_sha256": manifest["source_content_sha256"], "solar_transfer_status": manifest["solar_transfer_status"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--baseline-dir", type=Path, help="Frozen pre-change snapshot; refresh only approved PCH/SMR records")
    args = parser.parse_args()
    print(json.dumps(sync(args.source_dir, baseline=args.baseline_dir)))


if __name__ == "__main__":
    main()
