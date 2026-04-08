"""Tests del informe textual de integración SAND."""

from __future__ import annotations

import zipfile
from io import BytesIO

import pandas as pd
import pytest

from app.services.integrate_sand_log import (
    append_conflicts_lines,
    build_fatal_error_log,
    build_integration_sand_log,
    extract_contribution_with_combinaciones,
)
import numpy as np

from app.services.integrate_sand_cambios_excel import build_conflictos_workbook_bytes
from app.services.integrate_sand_service import (
    KEY_COLS,
    IntegrateSandService,
    _drop_keys,
    _normalize_value_column_names,
    _read_parameters_from_bytes,
)


def _minimal_sand_excel_bytes(rows: list[dict]) -> bytes:
    buf = BytesIO()
    pd.DataFrame(rows).to_excel(buf, sheet_name="Parameters", index=False, engine="openpyxl")
    return buf.getvalue()


def _sand_row(**kwargs: object) -> dict:
    row = {k: "" for k in KEY_COLS}
    row["2022"] = 1.0
    row.update(kwargs)
    return row


def test_build_integration_sand_log_contains_sections() -> None:
    contrib = extract_contribution_with_combinaciones(pd.DataFrame(), "nuevo.xlsm")

    text = build_integration_sand_log(
        base_filename="base.xlsm",
        paths_new=["nuevo.xlsm"],
        output_filename="SAND_integrado.xlsx",
        drop_techs=[],
        drop_fuels=[],
        n_base_rows=100,
        new_rows_counts=[50],
        duplicate_messages=[],
        conflicts=[],
        integration_rows=[
            {
                "filename": "nuevo.xlsm",
                "counts": {"NUEVA": 0, "ELIMINADA": 0, "MODIFICADA": 0},
                "seconds": 0.1,
                "unapplied": [],
            }
        ],
        contributions_for_log=[contrib],
        unapplied_all=[],
        warnings_validation_line="Todos los cambios se aplicaron correctamente.",
        drop_tech_rows=0,
        drop_fuel_rows=0,
        n_rows_before_drop=100,
        n_rows_final=100,
        had_drop=False,
        timing={"read": 0.1, "conflicts": 0.0, "integrate": 0.2, "export": 0.05, "total": 0.4},
        errors=[],
        read_errors=[],
    )

    assert "INTEGRACIÓN MÚLTIPLE SAND (API)" in text
    assert "Sin conflictos" in text
    assert "RESUMEN DE CONTRIBUCIONES POR ARCHIVO" in text
    assert "TABLA RESUMEN" in text


def test_append_conflicts_lines_modified() -> None:
    lines: list[str] = []
    conflicts = [
        {
            "tipo": "MODIFICADA",
            "columna": "2025",
            "Parameter": "Cap",
            "TECHNOLOGY": "TA",
            "FUEL": "OIL",
            "archivos": {"a.xlsm": 1.0, "b.xlsm": 2.0},
        }
    ]
    append_conflicts_lines(conflicts, lines)
    joined = "\n".join(lines)
    assert "CONFLICTOS DETECTADOS" in joined
    assert "CELDAS MODIFICADAS EN CONFLICTO" in joined


def test_build_fatal_error_log() -> None:
    t = build_fatal_error_log("base.xlsm", ["n1.xlsm"], ["Error X"])
    assert "ERROR" in t
    assert "base.xlsm" in t
    assert "Error X" in t


def test_normalize_value_column_names_int_and_float_years() -> None:
    df = pd.DataFrame([[1.0, 2.0, 3.0]], columns=["Parameter", 2022, 2023])
    out = _normalize_value_column_names(df)
    assert "2022" in out.columns and "2023" in out.columns
    assert 2022 not in out.columns and 2023 not in out.columns

    df2 = pd.DataFrame([[1.0]], columns=[2022.0])
    out2 = _normalize_value_column_names(df2)
    assert list(out2.columns) == ["2022"]

    df3 = pd.DataFrame([[1.0]], columns=[np.int64(2024)])
    assert "2024" in list(_normalize_value_column_names(df3).columns)


def test_normalize_value_column_names_string_years_unchanged() -> None:
    df = pd.DataFrame([[1.0, 2.0]], columns=["2022", "2023"])
    out = _normalize_value_column_names(df)
    assert list(out.columns) == ["2022", "2023"]


def test_normalize_drops_duplicate_int_and_str_same_year() -> None:
    df = pd.DataFrame([[1.0, 2.0]], columns=[2022, "2022"])
    out = _normalize_value_column_names(df)
    assert list(out.columns) == ["2022"]
    assert float(out.iloc[0, 0]) == 2.0


def test_read_parameters_from_bytes_applies_year_normalization() -> None:
    raw = pd.DataFrame([[1.0, 2.0]], columns=["Parameter", 2025])
    buf = BytesIO()
    raw.to_excel(buf, sheet_name="Parameters", index=False, engine="openpyxl")
    df = _read_parameters_from_bytes(buf.getvalue())
    assert "2025" in df.columns
    assert 2025 not in df.columns
    assert pd.api.types.is_numeric_dtype(df["2025"])


def test_integrate_sand_fatal_error_no_excel_output(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_a: object, **_k: object) -> None:
        raise KeyError("forced")

    monkeypatch.setattr("app.services.integrate_sand_service._detect_diffs", _boom)
    base_bytes = _minimal_sand_excel_bytes([_sand_row(Parameter="CapCost", TECHNOLOGY="TECH_A")])
    new_bytes = _minimal_sand_excel_bytes([_sand_row(Parameter="CapCost", TECHNOLOGY="TECH_A")])
    result = IntegrateSandService.integrate_sand_files(
        base_filename="base.xlsx",
        base_content=base_bytes,
        new_files=[("new.xlsx", new_bytes)],
    )
    assert result.get("integration_failed") is True
    assert result.get("output_content") == b""
    assert result.get("total_filas") == 0
    assert result.get("errors")
    assert "ERROR FATAL" in result["errors"][0]
    assert result.get("export_verification") is None


def test_drop_keys_removed_rows_and_motivo() -> None:
    df = pd.DataFrame(
        {
            "TECHNOLOGY": ["T1", "T1", "T2", "T3"],
            "FUEL": ["F1", "X", "F2", "F3"],
            "extra": [1, 2, 3, 4],
        }
    )
    out, n_tech, n_fuel, rem = _drop_keys(df, ["T1"], ["F2"])
    assert n_tech == 2
    assert n_fuel == 1
    assert len(out) == 1
    assert out.iloc[0]["TECHNOLOGY"] == "T3"
    assert len(rem) == 3
    assert set(rem["motivo_eliminacion"].unique()) == {"TECHNOLOGY", "FUEL"}
    assert (rem[rem["TECHNOLOGY"] == "T1"]["motivo_eliminacion"] == "TECHNOLOGY").all()
    assert (rem[(rem["TECHNOLOGY"] == "T2")]["motivo_eliminacion"] == "FUEL").all()


def test_cambios_excel_omits_eliminada_and_reports_drop_sheet() -> None:
    """Diffs pueden incluir ELIMINADA (clave en base, ausente en nuevo); no va al Excel de cambios."""
    base_rows = [
        _sand_row(Parameter="CapCost", TECHNOLOGY="TECH_A"),
        _sand_row(Parameter="CapCost", TECHNOLOGY="TECH_B"),
    ]
    new_rows = [_sand_row(Parameter="CapCost", TECHNOLOGY="TECH_B")]
    base_bytes = _minimal_sand_excel_bytes(base_rows)
    new_bytes = _minimal_sand_excel_bytes(new_rows)
    result = IntegrateSandService.integrate_sand_files(
        base_filename="base.xlsx",
        base_content=base_bytes,
        new_files=[("new.xlsx", new_bytes)],
        drop_techs_csv="TECH_A",
    )
    assert result.get("integration_failed") is not True
    cambios = result.get("cambios_excel_content") or b""
    assert len(cambios) > 100
    buf = BytesIO(cambios)
    df_cambios = pd.read_excel(buf, sheet_name="Cambios_vs_base")
    if "tipo_cambio" in df_cambios.columns:
        assert (df_cambios["tipo_cambio"] == "ELIMINADA").sum() == 0
    buf.seek(0)
    raw_drop = pd.read_excel(buf, sheet_name="Eliminaciones_drop", header=None)
    flat = [str(x) for x in raw_drop.values.ravel() if pd.notna(x)]
    joined = " ".join(flat)
    assert "TECH_A" in joined
    assert "motivo_eliminacion" in joined
    assert "TECHNOLOGY" in joined


def test_build_conflictos_workbook_bytes_non_empty() -> None:
    b = build_conflictos_workbook_bytes(
        [
            {
                "tipo": "MODIFICADA",
                "columna": "2022",
                "archivos": {"a.xlsm": 1.0, "b.xlsm": 2.0},
                **{k: "" for k in KEY_COLS},
            }
        ]
    )
    assert len(b) > 80


def test_integrate_two_new_files_conflict_skips_cambios_excel() -> None:
    """Con disputa entre archivos nuevos no se genera cambios_integracion.xlsx en memoria."""
    base_bytes = _minimal_sand_excel_bytes([_sand_row(Parameter="CapCost", TECHNOLOGY="T")])
    new_a = _minimal_sand_excel_bytes([_sand_row(Parameter="CapCost", TECHNOLOGY="T", **{"2022": 2.0})])
    new_b = _minimal_sand_excel_bytes([_sand_row(Parameter="CapCost", TECHNOLOGY="T", **{"2022": 3.0})])
    result = IntegrateSandService.integrate_sand_files(
        base_filename="base.xlsx",
        base_content=base_bytes,
        new_files=[("a.xlsx", new_a), ("b.xlsx", new_b)],
    )
    assert result["conflictos_count"] >= 1
    assert (result.get("cambios_excel_content") or b"") == b""


def test_integrate_sand_files_returns_log_text() -> None:
    base_bytes = _minimal_sand_excel_bytes([_sand_row(Parameter="CapCost", TECHNOLOGY="TECH_A")])
    new_bytes = _minimal_sand_excel_bytes([_sand_row(Parameter="CapCost", TECHNOLOGY="TECH_A")])
    result = IntegrateSandService.integrate_sand_files(
        base_filename="base.xlsx",
        base_content=base_bytes,
        new_files=[("new.xlsx", new_bytes)],
    )
    assert "log_text" in result
    assert "cambios_excel_content" in result
    assert len(result.get("cambios_excel_content") or b"") > 100
    assert "INTEGRACIÓN MÚLTIPLE SAND (API)" in result["log_text"]
    assert len(result["log_text"]) > 80


def test_integrate_sand_export_verification_ok() -> None:
    """Doble verificación del Excel exportado: coincide con diffs vs base."""
    base_bytes = _minimal_sand_excel_bytes([_sand_row(Parameter="CapCost", TECHNOLOGY="TECH_A")])
    new_bytes = _minimal_sand_excel_bytes(
        [_sand_row(Parameter="CapCost", TECHNOLOGY="TECH_B", **{"2022": 1.0})]
    )
    result = IntegrateSandService.integrate_sand_files(
        base_filename="base.xlsx",
        base_content=base_bytes,
        new_files=[("new.xlsx", new_bytes)],
    )
    ev = result.get("export_verification")
    assert ev is not None
    assert ev["ok"] is True
    assert ev["applies_to_download"] is True
    assert ev["verification_error"] is None
    assert ev["total_faltantes"] == 0
    assert len(ev["per_file"]) == 1
    assert ev["per_file"][0]["ok"] is True


def test_integrate_sand_export_verification_applies_false_when_conflicts() -> None:
    """Con conflictos el ZIP no incluye el integrado; applies_to_download es false."""
    base_bytes = _minimal_sand_excel_bytes([_sand_row(Parameter="CapCost", TECHNOLOGY="T")])
    new_a = _minimal_sand_excel_bytes([_sand_row(Parameter="CapCost", TECHNOLOGY="T", **{"2022": 2.0})])
    new_b = _minimal_sand_excel_bytes([_sand_row(Parameter="CapCost", TECHNOLOGY="T", **{"2022": 3.0})])
    result = IntegrateSandService.integrate_sand_files(
        base_filename="base.xlsx",
        base_content=base_bytes,
        new_files=[("a.xlsx", new_a), ("b.xlsx", new_b)],
    )
    ev = result.get("export_verification")
    assert ev is not None
    assert ev["applies_to_download"] is False


def test_zip_contains_txt_and_xlsx() -> None:
    """Misma estructura que el endpoint: ZIP con xlsx + integracion_sand_log.txt + cambios_integracion.xlsx."""
    xlsx_bytes = b"PK\x03\x04fake"
    log_txt = "linea1\nlinea2\n"
    cambios_bytes = b"PK\x03\x04cambios"
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SAND_integrado.xlsx", xlsx_bytes)
        zf.writestr("integracion_sand_log.txt", log_txt.encode("utf-8"))
        zf.writestr("cambios_integracion.xlsx", cambios_bytes)
    buf.seek(0)
    with zipfile.ZipFile(buf, "r") as zf:
        names = set(zf.namelist())
        assert "integracion_sand_log.txt" in names
        assert "SAND_integrado.xlsx" in names
        assert "cambios_integracion.xlsx" in names
        assert zf.read("integracion_sand_log.txt").decode("utf-8") == log_txt


def test_verify_integrated_export_standalone_matches_integration_output() -> None:
    base_bytes = _minimal_sand_excel_bytes([_sand_row(Parameter="CapCost", TECHNOLOGY="TECH_A")])
    new_bytes = _minimal_sand_excel_bytes([_sand_row(Parameter="CapCost", TECHNOLOGY="TECH_B", **{"2022": 1.0})])
    integrated = IntegrateSandService.integrate_sand_files(
        base_filename="base.xlsx",
        base_content=base_bytes,
        new_files=[("new.xlsx", new_bytes)],
    )
    out = integrated["output_content"]
    vr = IntegrateSandService.verify_integrated_export_standalone(
        base_filename="base.xlsx",
        base_content=base_bytes,
        integrated_filename="integrado.xlsx",
        integrated_content=out,
        new_files=[("new.xlsx", new_bytes)],
    )
    assert vr["export_verification"]["ok"] is True


def test_verify_integrated_export_standalone_detects_missing_row() -> None:
    base_bytes = _minimal_sand_excel_bytes([_sand_row(Parameter="CapCost", TECHNOLOGY="TECH_A")])
    new_bytes = _minimal_sand_excel_bytes([_sand_row(Parameter="CapCost", TECHNOLOGY="TECH_B", **{"2022": 1.0})])
    wrong_integrated = base_bytes
    vr = IntegrateSandService.verify_integrated_export_standalone(
        base_filename="base.xlsx",
        base_content=base_bytes,
        integrated_filename="bad.xlsx",
        integrated_content=wrong_integrated,
        new_files=[("new.xlsx", new_bytes)],
    )
    assert vr["export_verification"]["ok"] is False
    assert vr["export_verification"]["total_faltantes"] > 0
