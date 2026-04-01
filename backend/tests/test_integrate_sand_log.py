"""Tests del informe textual de integración SAND."""

from __future__ import annotations

import zipfile
from io import BytesIO

import pandas as pd

from app.services.integrate_sand_log import (
    append_conflicts_lines,
    build_fatal_error_log,
    build_integration_sand_log,
    extract_contribution_with_combinaciones,
)
from app.services.integrate_sand_service import KEY_COLS, IntegrateSandService


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
