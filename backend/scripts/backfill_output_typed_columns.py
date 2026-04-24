"""Backfill de columnas tipadas en `osemosys_output_param_value`.

Lee ``index_json`` de filas donde las columnas tipadas (id_technology,
id_fuel, year, ...) son NULL, decodifica posiciones usando
``VARIABLE_INDEX_NAMES`` y las lookups de catálogo, y hace UPDATE.

Idempotente: cada fila se actualiza una sola vez y sólo se tocan filas
donde AL MENOS una columna tipada relevante sigue NULL.

Uso dentro del contenedor api:

    docker compose exec api python scripts/backfill_output_typed_columns.py --job-id 17
    docker compose exec api python scripts/backfill_output_typed_columns.py --all
    docker compose exec api python scripts/backfill_output_typed_columns.py --all --dry-run
"""

from __future__ import annotations

import argparse
import logging
from collections import defaultdict
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    Dailytimebracket,
    Daytype,
    Emission,
    Fuel,
    ModeOfOperation,
    OsemosysOutputParamValue,
    Region,
    Season,
    SimulationJob,
    StorageSet,
    Technology,
    Timeslice,
)
from app.simulation.core.results_processing import VARIABLE_INDEX_NAMES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill")


_DIM_TO_ID_COL: dict[str, str] = {
    "REGION": "id_region",
    "TECHNOLOGY": "id_technology",
    "FUEL": "id_fuel",
    "EMISSION": "id_emission",
    "TIMESLICE": "id_timeslice",
    "MODE_OF_OPERATION": "id_mode_of_operation",
    "SEASON": "id_season",
    "DAYTYPE": "id_daytype",
    "DAILYTIMEBRACKET": "id_dailytimebracket",
    "STORAGE": "id_storage",
}

_DIM_TO_NAME_COL: dict[str, str] = {
    "TECHNOLOGY": "technology_name",
    "FUEL": "fuel_name",
    "EMISSION": "emission_name",
}


def _load_lookups(db: Session) -> dict[str, dict[str, int]]:
    """Carga los mapeos nombre→id para cada catálogo."""
    _specs = [
        ("REGION", Region, "name"),
        ("TECHNOLOGY", Technology, "name"),
        ("FUEL", Fuel, "name"),
        ("EMISSION", Emission, "name"),
        ("TIMESLICE", Timeslice, "code"),
        ("MODE_OF_OPERATION", ModeOfOperation, "code"),
        ("SEASON", Season, "code"),
        ("DAYTYPE", Daytype, "code"),
        ("DAILYTIMEBRACKET", Dailytimebracket, "code"),
        ("STORAGE", StorageSet, "code"),
    ]
    out: dict[str, dict[str, int]] = {}
    for key, model_cls, attr in _specs:
        rows = db.execute(select(model_cls.id, getattr(model_cls, attr))).all()
        out[key] = {str(name): int(pk) for pk, name in rows if name is not None}
    return out


def _safe_int(x: Any) -> int | None:
    if x is None:
        return None
    if isinstance(x, bool):
        return int(x)
    if isinstance(x, int):
        return x
    if isinstance(x, float):
        return int(x)
    try:
        text = str(x).strip()
        if not text:
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _decode_row(
    variable_name: str,
    index_json: Any,
    lookups: dict[str, dict[str, int]],
) -> dict[str, Any] | None:
    """Convierte index_json a dict de columnas tipadas según el registry.

    Retorna None si la variable no está en el registry o la forma no cuadra.
    """
    dims = VARIABLE_INDEX_NAMES.get(variable_name)
    if not dims:
        return None
    if not isinstance(index_json, list):
        return None
    if len(index_json) != len(dims):
        return None

    result: dict[str, Any] = {}
    for dim, raw_val in zip(dims, index_json):
        if raw_val is None or raw_val == "":
            continue
        if dim == "YEAR":
            y = _safe_int(raw_val)
            if y is not None:
                result["year"] = y
            continue
        name = str(raw_val)
        id_col = _DIM_TO_ID_COL.get(dim)
        if id_col:
            lk = lookups.get(dim, {})
            lid = lk.get(name)
            if lid is not None:
                result[id_col] = int(lid)
        name_col = _DIM_TO_NAME_COL.get(dim)
        if name_col:
            result[name_col] = name
    return result or None


def _jobs_to_process(db: Session, *, job_id: int | None, all_jobs: bool) -> list[int]:
    if job_id is not None:
        return [job_id]
    if not all_jobs:
        raise SystemExit("Usa --job-id N o --all")
    rows = db.execute(
        select(SimulationJob.id)
        .where(SimulationJob.status == "SUCCEEDED")
        .order_by(SimulationJob.id.asc())
    ).all()
    return [int(r[0]) for r in rows]


def _process_job(
    db: Session,
    job_id: int,
    lookups: dict[str, dict[str, int]],
    *,
    dry_run: bool,
    batch_size: int = 2000,
) -> dict[str, int]:
    """Procesa un job. Retorna métricas por variable."""
    # Seleccionar filas que necesitan backfill:
    # - index_json no nulo
    # - año nulo O tecnología nula O región nula (al menos una columna clave)
    rows = (
        db.query(
            OsemosysOutputParamValue.id,
            OsemosysOutputParamValue.variable_name,
            OsemosysOutputParamValue.index_json,
            OsemosysOutputParamValue.year,
            OsemosysOutputParamValue.id_region,
            OsemosysOutputParamValue.id_technology,
        )
        .filter(
            OsemosysOutputParamValue.id_simulation_job == job_id,
            OsemosysOutputParamValue.index_json.is_not(None),
        )
        .yield_per(5000)
    )

    counts: dict[str, int] = defaultdict(int)
    pending_updates: list[dict[str, Any]] = []

    for row in rows:
        # skip si todas las columnas clave ya están pobladas
        if row.year is not None and row.id_region is not None:
            counts[f"{row.variable_name}::already_typed"] += 1
            continue
        decoded = _decode_row(row.variable_name, row.index_json, lookups)
        if not decoded:
            counts[f"{row.variable_name}::no_decode"] += 1
            continue
        pending_updates.append({"_id": row.id, **decoded})
        counts[f"{row.variable_name}::to_update"] += 1

    if dry_run:
        logger.info(
            "[job %s] dry-run — %s filas a actualizar",
            job_id,
            sum(
                v
                for k, v in counts.items()
                if k.endswith("::to_update")
            ),
        )
        return dict(counts)

    # Aplicar updates por batches.
    for i in range(0, len(pending_updates), batch_size):
        chunk = pending_updates[i : i + batch_size]
        for item in chunk:
            item_id = item.pop("_id")
            db.execute(
                update(OsemosysOutputParamValue)
                .where(OsemosysOutputParamValue.id == item_id)
                .values(**item)
            )
        db.flush()
    db.commit()

    return dict(counts)


def _summarize(label: str, counts: dict[str, int]) -> None:
    logger.info("%s — resumen:", label)
    by_var: dict[str, dict[str, int]] = defaultdict(dict)
    for k, v in counts.items():
        var, _, kind = k.partition("::")
        by_var[var][kind] = v
    for var in sorted(by_var):
        parts = by_var[var]
        logger.info(
            "  %-45s  updated=%d  already=%d  skipped=%d",
            var,
            parts.get("to_update", 0),
            parts.get("already_typed", 0),
            parts.get("no_decode", 0),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", type=int, help="ID de un job específico")
    parser.add_argument("--all", action="store_true", help="Todos los jobs SUCCEEDED")
    parser.add_argument("--dry-run", action="store_true", help="Sólo reporta, no actualiza")
    args = parser.parse_args()

    with SessionLocal() as db:
        lookups = _load_lookups(db)
        jobs = _jobs_to_process(db, job_id=args.job_id, all_jobs=args.all)
        logger.info("Procesando %d jobs: %s", len(jobs), jobs)
        total_counts: dict[str, int] = defaultdict(int)
        for jid in jobs:
            logger.info("=== Job %d ===", jid)
            counts = _process_job(db, jid, lookups, dry_run=args.dry_run)
            _summarize(f"Job {jid}", counts)
            for k, v in counts.items():
                total_counts[k] += v
        if len(jobs) > 1:
            _summarize("TOTAL", dict(total_counts))
        if args.dry_run:
            logger.info("DRY-RUN terminado — ningún cambio aplicado.")
        else:
            logger.info("Backfill completado.")


if __name__ == "__main__":
    main()
