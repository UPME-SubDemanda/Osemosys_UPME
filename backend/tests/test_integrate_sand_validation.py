from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from app.services.integrate_sand_service import IntegrateSandService, KEY_COLS


REFERENCE_DIR = Path(r"C:\Users\jchav\OneDrive\Documentos\Trabajo UPME\Codigos David Adapatar\Concatenar excel")
REFERENCE_SCRIPT_DIR = REFERENCE_DIR
REFERENCE_SAND_DIR = REFERENCE_DIR / "SAND"
REFERENCE_SCENARIO_DIR = REFERENCE_SAND_DIR / "PA 2"
REFERENCE_BASE_FILE = REFERENCE_SAND_DIR / "SAND_20_02_2026.xlsm"


def _read_parameters(path: Path) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name="Parameters", engine="calamine")


@pytest.mark.skipif(not REFERENCE_DIR.exists(), reason="No existe la carpeta del código de referencia.")
def test_reference_vs_new_integrate_sand_same_output() -> None:
    assert REFERENCE_BASE_FILE.exists(), "No existe el archivo base de referencia."
    assert REFERENCE_SCENARIO_DIR.exists(), "No existe la carpeta de archivos SAND de escenario."

    reference_script_path = str(REFERENCE_SCRIPT_DIR)
    if reference_script_path not in sys.path:
        sys.path.insert(0, reference_script_path)

    from integrate_multi_sand import integrate_multi  # type: ignore[import-not-found]

    with tempfile.TemporaryDirectory() as tmpdir:
        reference_output = Path(tmpdir) / "reference_integrated.xlsx"

        reference_df, _, _ = integrate_multi(
            folder=str(REFERENCE_SCENARIO_DIR),
            path_base=str(REFERENCE_BASE_FILE),
            output=str(reference_output),
            drop_techs=[],
            drop_fuels=[],
        )
        assert reference_df is not None
        assert reference_output.exists(), "No se generó la salida de la implementación de referencia."

        base_content = REFERENCE_BASE_FILE.read_bytes()
        new_paths = sorted(
            p
            for p in REFERENCE_SCENARIO_DIR.glob("*.xls*")
            if not p.name.lower().startswith("sand_integrado") and not p.name.startswith("~$")
        )
        assert len(new_paths) > 0, "No hay archivos SAND nuevos para validar."
        new_files = [(path.name, path.read_bytes()) for path in new_paths]

        new_result = IntegrateSandService.integrate_sand_files(
            base_filename=REFERENCE_BASE_FILE.name,
            base_content=base_content,
            new_files=new_files,
            drop_techs_csv=None,
            drop_fuels_csv=None,
        )

        new_output = Path(tmpdir) / "new_integrated.xlsx"
        new_output.write_bytes(new_result["output_content"])
        assert new_output.exists(), "No se generó la salida de la nueva implementación."

        df_reference = _read_parameters(reference_output)
        df_new = _read_parameters(new_output)

        assert list(df_reference.columns) == list(df_new.columns), "Las columnas no coinciden entre ambas salidas."
        assert len(df_reference) == len(df_new), "El número de filas no coincide entre ambas salidas."

        sort_cols = [col for col in KEY_COLS if col in df_reference.columns]
        if sort_cols:
            df_reference = df_reference.sort_values(sort_cols).reset_index(drop=True)
            df_new = df_new.sort_values(sort_cols).reset_index(drop=True)

        # Comparación final estricta de datos (mismos valores, filas y columnas).
        assert_frame_equal(df_reference, df_new, check_dtype=False, check_like=False)
