"""Copy an approved central factor build into the checksum-verified runtime snapshot."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

FILES = ("employment_factors_model_default_2024_2055.csv", "technology_assumptions_2024.csv")
DESTINATION = Path(__file__).resolve().parents[1] / "app/data/employment_factor_snapshot"


def sync(source: Path, destination: Path = DESTINATION) -> dict:
    manifest_path = source / "employment_factor_provenance.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["scenario"] != "central" or manifest.get("productivity_transfer") != "selective" or manifest["solar_projection"] != "catalogue":
        raise ValueError("Only the approved central/selective/catalogue build may become the runtime snapshot")
    for name in FILES:
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != manifest["output_sha256"][name]:
            raise ValueError(f"Source data checksum mismatch: {name}")
    destination.mkdir(parents=True, exist_ok=True)
    for name in (*FILES, manifest_path.name):
        shutil.copyfile(source / name, destination / name)
    return {"destination": str(destination), "source_revision": manifest["source_revision"],
            "source_content_sha256": manifest["source_content_sha256"], "solar_transfer_status": manifest["solar_transfer_status"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(sync(args.source_dir)))


if __name__ == "__main__":
    main()
