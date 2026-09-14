#!/usr/bin/env python3
"""Benchmark local de export-raw: tiempo, RSS y tamaño del archivo."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import SessionLocal
from app.services.simulation_results_export_service import export_raw_data_to_excel_file


def _read_rss_kb() -> int | None:
    status_path = Path("/proc/self/status")
    if not status_path.exists():
        return None
    for line in status_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark export-raw Excel generation")
    parser.add_argument("job_id", type=int, help="ID del simulation_job")
    args = parser.parse_args()

    fd, tmp_path = tempfile.mkstemp(suffix=".xlsx", prefix="benchmark_export_raw_")
    os.close(fd)
    rss_before = _read_rss_kb()
    t0 = time.perf_counter()
    try:
        with SessionLocal() as db:
            row_count = export_raw_data_to_excel_file(
                db, job_id=args.job_id, output_path=tmp_path
            )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        elapsed = time.perf_counter() - t0
        rss_after = _read_rss_kb()
        size_bytes = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    print(f"job_id={args.job_id}")
    print(f"rows={row_count}")
    print(f"elapsed_seconds={elapsed:.2f}")
    print(f"file_size_mb={size_bytes / (1024 * 1024):.2f}")
    if rss_before is not None and rss_after is not None:
        print(f"rss_before_mb={rss_before / 1024:.1f}")
        print(f"rss_after_mb={rss_after / 1024:.1f}")
        print(f"rss_delta_mb={(rss_after - rss_before) / 1024:.1f}")
    if row_count > 0:
        print(f"rows_per_second={row_count / elapsed:.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
