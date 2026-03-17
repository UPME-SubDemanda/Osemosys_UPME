"""Orquestacion del pipeline completo de simulacion OSeMOSYS.

Coordina el flujo transaccional de una corrida:
  1. Carga datos del escenario desde PostgreSQL (osemosys_param_value).
  2. Preprocesa y construye modelo Pyomo con sets, parametros y restricciones.
  3. Resuelve el modelo con el solver configurado (HiGHS, GLPK, etc.).
  4. Extrae resultados (dispatch, new_capacity, emisiones, etc.).
  5. Persiste resultados en la tabla osemosys_output_param_value y metadatos
     de resumen en simulation_job.

Arquitectura:
  - Ejecuta desde worker Celery (no desde request HTTP).
  - Cancelacion cooperativa entre etapas.
  - Resultados almacenados en BD (no en filesystem).
"""

from __future__ import annotations

import logging
from time import perf_counter
from typing import Any, Final

from sqlalchemy import func, insert
from sqlalchemy.orm import Session

from app.models import OsemosysParamValue, OsemosysOutputParamValue, SimulationJob
from app.repositories.simulation_repository import SimulationRepository
from app.simulation.osemosys_core import run_osemosys_from_db

logger = logging.getLogger(__name__)

STAGE_EXTRACT_DATA: Final[str] = "extract_data"
STAGE_BUILD_MODEL: Final[str] = "build_model"
STAGE_SOLVE: Final[str] = "solve"
STAGE_PERSIST_RESULTS: Final[str] = "persist_results"
STAGE_CANCEL: Final[str] = "cancel"

BATCH_SIZE: Final[int] = 2000


def _check_cancel_requested(db: Session, *, job_id: int) -> None:
    """Evalua cancelacion cooperativa y corta la ejecucion si aplica."""
    job = SimulationRepository.get_job_by_id(db, job_id=job_id)
    if job and job.cancel_requested and job.status in ("QUEUED", "RUNNING"):
        job.status = "CANCELLED"
        job.finished_at = func.now()
        SimulationRepository.add_event(
            db,
            job_id=job_id,
            event_type="INFO",
            stage=STAGE_CANCEL,
            message="Simulacion cancelada por el usuario.",
            progress=job.progress,
        )
        db.commit()
        raise RuntimeError("JOB_CANCELLED")


def _build_output_rows(
    solution: dict[str, Any],
    job_id: int,
) -> list[dict]:
    """Construye la lista de dicts para bulk insert en osemosys_output_param_value."""
    rows: list[dict] = []

    for row in solution.get("dispatch", []):
        rows.append({
            "id_simulation_job": job_id,
            "variable_name": "Dispatch",
            "id_region": row.get("region_id"),
            "id_technology": row.get("technology_id"),
            "technology_name": row.get("technology_name"),
            "fuel_name": row.get("fuel_name"),
            "year": row.get("year"),
            "value": float(row.get("dispatch", 0.0)),
            "value2": float(row.get("cost", 0.0)),
            "index_json": None,
        })

    for row in solution.get("new_capacity", []):
        rows.append({
            "id_simulation_job": job_id,
            "variable_name": "NewCapacity",
            "id_region": row.get("region_id"),
            "id_technology": row.get("technology_id"),
            "technology_name": row.get("technology_name"),
            "fuel_name": None,
            "year": row.get("year"),
            "value": float(row.get("new_capacity", 0.0)),
            "value2": None,
            "index_json": None,
        })

    for row in solution.get("unmet_demand", []):
        rows.append({
            "id_simulation_job": job_id,
            "variable_name": "UnmetDemand",
            "id_region": row.get("region_id"),
            "id_technology": None,
            "technology_name": None,
            "fuel_name": None,
            "year": row.get("year"),
            "value": float(row.get("unmet_demand", 0.0)),
            "value2": None,
            "index_json": None,
        })

    for row in solution.get("annual_emissions", []):
        rows.append({
            "id_simulation_job": job_id,
            "variable_name": "AnnualEmissions",
            "id_region": row.get("region_id"),
            "id_technology": None,
            "technology_name": None,
            "fuel_name": None,
            "year": row.get("year"),
            "value": float(row.get("annual_emissions", 0.0)),
            "value2": None,
            "index_json": None,
        })

    for var_name, entries in solution.get("intermediate_variables", {}).items():
        for entry in entries:
            rows.append({
                "id_simulation_job": job_id,
                "variable_name": var_name,
                "id_region": None,
                "id_technology": None,
                "technology_name": None,
                "fuel_name": None,
                "emission_name": None,
                "year": None,
                "value": float(entry.get("value", 0.0)),
                "value2": None,
                "index_json": entry.get("index"),
            })

    return rows


def run_pipeline(db: Session, *, job_id: int) -> None:
    """Ejecuta una corrida completa de simulacion para un job especifico.

    Persiste resultados en BD (simulation_job + osemosys_output_param_value).
    """
    stage_times: dict[str, float] = {}
    t0 = perf_counter()
    job = SimulationRepository.get_job_by_id(db, job_id=job_id)
    if not job:
        raise RuntimeError("SIMULATION_JOB_NOT_FOUND")

    # ------------------------------------------------------------------
    # ETAPA 1: EXTRACCION DE DATOS DE ENTRADA
    # ------------------------------------------------------------------
    SimulationRepository.add_event(
        db,
        job_id=job_id,
        event_type="STAGE",
        stage=STAGE_EXTRACT_DATA,
        message="Extrayendo datos de entrada del escenario.",
        progress=5.0,
    )
    db.commit()
    _check_cancel_requested(db, job_id=job_id)

    osemosys_agg_rows = (
        db.query(
            OsemosysParamValue.param_name,
            OsemosysParamValue.year,
            func.count().label("records"),
            func.sum(OsemosysParamValue.value).label("total_value"),
        )
        .filter(OsemosysParamValue.id_scenario == job.scenario_id)
        .group_by(OsemosysParamValue.param_name, OsemosysParamValue.year)
        .all()
    )
    osemosys_total_count = sum(r.records for r in osemosys_agg_rows)
    osemosys_inputs_summary = sorted(
        [
            {
                "param_name": str(r.param_name),
                "year": int(r.year) if r.year is not None else None,
                "records": int(r.records),
                "total_value": float(r.total_value or 0.0),
            }
            for r in osemosys_agg_rows
        ],
        key=lambda x: (x["param_name"], x["year"] if x["year"] is not None else -1),
    )

    job.progress = 15.0
    SimulationRepository.add_event(
        db,
        job_id=job_id,
        event_type="STAGE",
        stage=STAGE_EXTRACT_DATA,
        message=f"Se cargaron {osemosys_total_count} registros de osemosys_param_value.",
        progress=job.progress,
    )
    db.commit()
    stage_times[f"{STAGE_EXTRACT_DATA}_seconds"] = perf_counter() - t0

    # ------------------------------------------------------------------
    # ETAPA 2: CONSTRUCCION DEL MODELO
    # ------------------------------------------------------------------
    t1 = perf_counter()
    _check_cancel_requested(db, job_id=job_id)

    SimulationRepository.add_event(
        db,
        job_id=job_id,
        event_type="STAGE",
        stage=STAGE_BUILD_MODEL,
        message="Construyendo estructura de datos para optimizacion.",
        progress=20.0,
    )
    
    db.commit()
    job.progress = 40.0
    db.commit()
    stage_times[f"{STAGE_BUILD_MODEL}_seconds"] = perf_counter() - t1

    # ------------------------------------------------------------------
    # ETAPA 3: RESOLUCION DEL MODELO (SOLVE)
    # ------------------------------------------------------------------
    t2 = perf_counter()
    _check_cancel_requested(db, job_id=job_id)
    SimulationRepository.add_event(
        db,
        job_id=job_id,
        event_type="STAGE",
        stage=STAGE_SOLVE,
        message="Ejecutando optimizacion OSEMOSYS.",
        progress=45.0,
    )
    db.commit()

    def _on_stage(stage_name: str, stage_progress: float) -> None:
        job.progress = stage_progress
        SimulationRepository.add_event(
            db,
            job_id=job_id,
            event_type="STAGE",
            stage=stage_name,
            message=f"Bloque {stage_name} ejecutado.",
            progress=stage_progress,
        )
        db.commit()
        _check_cancel_requested(db, job_id=job_id)

    solution = run_osemosys_from_db(
        db,
        scenario_id=job.scenario_id,
        solver_name=job.solver_name,
        on_stage=_on_stage,
    )

    job.progress = 85.0
    SimulationRepository.add_event(
        db,
        job_id=job_id,
        event_type="INFO",
        stage=STAGE_SOLVE,
        message=(
            f"Solver: {solution['solver_status']} | "
            f"Coverage: {solution['coverage_ratio']:.2%}"
        ),
        progress=job.progress,
    )
    db.commit()
    stage_times[f"{STAGE_SOLVE}_seconds"] = perf_counter() - t2

    # ------------------------------------------------------------------
    # ETAPA 4: PERSISTENCIA DE RESULTADOS EN BD
    # ------------------------------------------------------------------
    t3 = perf_counter()
    _check_cancel_requested(db, job_id=job_id)
    SimulationRepository.add_event(
        db,
        job_id=job_id,
        event_type="STAGE",
        stage=STAGE_PERSIST_RESULTS,
        message="Persistiendo resultados en base de datos.",
        progress=90.0,
    )
    db.commit()

    # Summary metadata on simulation_job
    job.objective_value = solution.get("objective_value")
    job.coverage_ratio = solution.get("coverage_ratio")
    job.total_demand = solution.get("total_demand")
    job.total_dispatch = solution.get("total_dispatch")
    job.total_unmet = solution.get("total_unmet")
    job.records_used = osemosys_total_count
    job.osemosys_param_records = osemosys_total_count
    job.stage_times_json = stage_times
    _model_timings = dict(solution.get("model_timings", {}))
    _model_timings["solver_status"] = solution.get("solver_status", "unknown")
    job.model_timings_json = _model_timings
    job.inputs_summary_json = osemosys_inputs_summary

    # Bulk insert result rows in batches
    output_rows = _build_output_rows(solution, job_id=job.id)
    for i in range(0, len(output_rows), BATCH_SIZE):
        batch = output_rows[i : i + BATCH_SIZE]
        db.execute(insert(OsemosysOutputParamValue), batch)
        db.flush()

    stage_times[f"{STAGE_PERSIST_RESULTS}_seconds"] = perf_counter() - t3
    job.stage_times_json = stage_times

    logger.info(
        "Job %s: %d filas de resultado insertadas en osemosys_output_param_value",
        job_id,
        len(output_rows),
    )

    job.progress = 100.0
    db.commit()
