from __future__ import annotations

import statistics
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from io import BytesIO
from pathlib import Path
from time import perf_counter

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from app.services.integrate_sand_service import IntegrateSandService, KEY_COLS


REFERENCE_DIR = Path(r"C:\Users\jchav\OneDrive\Documentos\Trabajo UPME\Codigos David Adapatar\Concatenar excel")
REFERENCE_SAND_DIR = REFERENCE_DIR / "SAND"
REFERENCE_SCENARIO_DIR = REFERENCE_SAND_DIR / "PA 2"
REFERENCE_BASE_FILE = REFERENCE_SAND_DIR / "SAND_20_02_2026.xlsm"
N_RUNS = 3


def _read_parameters(path: Path) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name="Parameters", engine="calamine")


def _read_parameters_from_bytes(content: bytes) -> pd.DataFrame:
    return pd.read_excel(BytesIO(content), sheet_name="Parameters", engine="calamine")


def _normalize_for_compare(df: pd.DataFrame) -> pd.DataFrame:
    sort_cols = [col for col in KEY_COLS if col in df.columns]
    if sort_cols:
        return df.sort_values(sort_cols).reset_index(drop=True)
    return df.reset_index(drop=True)


def _summarize_ms(samples_s: list[float]) -> dict[str, float]:
    return {
        "min_ms": min(samples_s) * 1000,
        "mean_ms": statistics.mean(samples_s) * 1000,
        "max_ms": max(samples_s) * 1000,
    }


@pytest.mark.skipif(not REFERENCE_DIR.exists(), reason="No existe la carpeta del código de referencia.")
def test_benchmark_reference_vs_new_integration() -> None:
    assert REFERENCE_BASE_FILE.exists(), "No existe el archivo base de referencia."
    assert REFERENCE_SCENARIO_DIR.exists(), "No existe la carpeta de archivos SAND de escenario."

    reference_script_path = str(REFERENCE_DIR)
    if reference_script_path not in sys.path:
        sys.path.insert(0, reference_script_path)

    from integrate_multi_sand import integrate_multi  # type: ignore[import-not-found]

    base_content = REFERENCE_BASE_FILE.read_bytes()
    new_paths = sorted(
        p
        for p in REFERENCE_SCENARIO_DIR.glob("*.xls*")
        if not p.name.lower().startswith("sand_integrado") and not p.name.startswith("~$")
    )
    assert new_paths, "No hay archivos SAND nuevos para benchmark."
    new_files = [(path.name, path.read_bytes()) for path in new_paths]

    reference_times: list[float] = []
    new_times: list[float] = []
    last_reference_df: pd.DataFrame | None = None
    last_new_df: pd.DataFrame | None = None

    for _ in range(N_RUNS):
        with tempfile.TemporaryDirectory() as tmpdir:
            reference_output = Path(tmpdir) / "reference_integrated.xlsx"

            t0 = perf_counter()
            with redirect_stdout(BytesIOText()), redirect_stderr(BytesIOText()):
                reference_df, _, _ = integrate_multi(
                    folder=str(REFERENCE_SCENARIO_DIR),
                    path_base=str(REFERENCE_BASE_FILE),
                    output=str(reference_output),
                    drop_techs=[],
                    drop_fuels=[],
                )
            reference_elapsed = perf_counter() - t0
            assert reference_df is not None
            assert reference_output.exists(), "No se generó la salida de referencia."
            reference_times.append(reference_elapsed)

            t1 = perf_counter()
            new_result = IntegrateSandService.integrate_sand_files(
                base_filename=REFERENCE_BASE_FILE.name,
                base_content=base_content,
                new_files=new_files,
                drop_techs_csv=None,
                drop_fuels_csv=None,
            )
            new_elapsed = perf_counter() - t1
            new_times.append(new_elapsed)

            df_reference = _read_parameters(reference_output)
            df_new = _read_parameters_from_bytes(new_result["output_content"])

            df_reference = _normalize_for_compare(df_reference)
            df_new = _normalize_for_compare(df_new)
            assert_frame_equal(df_reference, df_new, check_dtype=False, check_like=False)

            last_reference_df = df_reference
            last_new_df = df_new

    assert last_reference_df is not None
    assert last_new_df is not None
    assert list(last_reference_df.columns) == list(last_new_df.columns)
    assert len(last_reference_df) == len(last_new_df)

    ref_summary = _summarize_ms(reference_times)
    new_summary = _summarize_ms(new_times)
    speedup = ref_summary["mean_ms"] / new_summary["mean_ms"] if new_summary["mean_ms"] > 0 else float("inf")
    delta_ms = new_summary["mean_ms"] - ref_summary["mean_ms"]

    print("\n--- Benchmark Integración SAND (ms) ---")
    print(
        f"Original  -> min: {ref_summary['min_ms']:.2f} | "
        f"mean: {ref_summary['mean_ms']:.2f} | max: {ref_summary['max_ms']:.2f}"
    )
    print(
        f"Nuevo     -> min: {new_summary['min_ms']:.2f} | "
        f"mean: {new_summary['mean_ms']:.2f} | max: {new_summary['max_ms']:.2f}"
    )
    print(f"Delta (nuevo-original): {delta_ms:.2f} ms")
    print(f"Speedup (original/nuevo): {speedup:.3f}x")


class BytesIOText:
    """Buffer de texto UTF-8 para redirigir salida y evitar errores de encoding en Windows."""

    def __init__(self) -> None:
        self._chunks: list[str] = []

    def write(self, s: str) -> int:
        self._chunks.append(str(s))
        return len(s)

    def flush(self) -> None:
        return None
