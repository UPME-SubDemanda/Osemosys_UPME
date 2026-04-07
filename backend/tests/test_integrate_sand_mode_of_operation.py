"""Regresión: MODE_OF_OPERATION canónico al leer/exportar Excel SAND integrado."""

from io import BytesIO

import pytest
from openpyxl import Workbook

from app.services.integrate_sand_service import _read_parameters_from_bytes


@pytest.mark.parametrize(
    "mode_val",
    [1.0, 1, "1", "1.0"],
)
def test_read_parameters_from_bytes_normalizes_mode_of_operation(mode_val):
    """Tras fillna/astype(str), 1.0 y 1 deben unificarse en '1'."""
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Parameters"
    ws.append(
        [
            "Parameter",
            "REGION",
            "TECHNOLOGY",
            "EMISSION",
            "MODE_OF_OPERATION",
            "FUEL",
            "TIMESLICE",
            "STORAGE",
            "REGION2",
            "2022",
        ]
    )
    ws.append(
        [
            "TestParam",
            "RE1",
            "ELC002",
            "",
            mode_val,
            "",
            "",
            "",
            "",
            0.0,
        ]
    )
    buf = BytesIO()
    wb.save(buf)
    df = _read_parameters_from_bytes(buf.getvalue())
    assert len(df) == 1
    assert df["MODE_OF_OPERATION"].iloc[0] == "1"
