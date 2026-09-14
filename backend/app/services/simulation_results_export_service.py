"""Exportación eficiente de resultados de simulación (streaming a disco)."""

from __future__ import annotations

import logging
from time import perf_counter

from fastapi import HTTPException
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.models import OsemosysOutputParamValue

logger = logging.getLogger(__name__)

_RAW_HEADERS = [
    "VariableName",
    "Technology",
    "Fuel",
    "Emission",
    "Year",
    "Value",
    "IndexJSON",
]

_YIELD_PER = 50_000


def export_raw_data_to_excel_file(
    db: Session,
    *,
    job_id: int,
    output_path: str,
) -> int:
    """Escribe Excel crudo a disco. Retorna número de filas exportadas."""
    t0 = perf_counter()
    query = (
        db.query(
            OsemosysOutputParamValue.variable_name,
            OsemosysOutputParamValue.technology_name,
            OsemosysOutputParamValue.fuel_name,
            OsemosysOutputParamValue.emission_name,
            OsemosysOutputParamValue.year,
            OsemosysOutputParamValue.value,
            OsemosysOutputParamValue.index_json,
        )
        .filter(OsemosysOutputParamValue.id_simulation_job == job_id)
    )

    wb = Workbook(write_only=True)
    ws = wb.create_sheet(title="Raw Data")
    ws.append(_RAW_HEADERS)

    row_count = 0
    for row in query.yield_per(_YIELD_PER):
        index_json = row.index_json
        ws.append(
            [
                row.variable_name,
                row.technology_name or "",
                row.fuel_name or "",
                row.emission_name or "",
                row.year,
                float(row.value) if row.value is not None else None,
                str(index_json) if index_json else "",
            ]
        )
        row_count += 1

    if row_count == 0:
        raise HTTPException(
            status_code=404,
            detail=(
                "No hay datos crudos disponibles para este escenario. "
                "La simulación puede no haber guardado resultados en la base de datos."
            ),
        )

    wb.save(output_path)
    logger.info(
        "export-raw job=%s rows=%s elapsed=%.1fs",
        job_id,
        row_count,
        perf_counter() - t0,
    )
    return row_count
