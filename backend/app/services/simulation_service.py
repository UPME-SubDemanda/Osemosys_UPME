"""Service de negocio para jobs de simulacion."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models import OsemosysOutputParamValue, Scenario, ScenarioTag, User
from app.repositories.simulation_repository import SimulationRepository
from app.services.docker_metrics_service import DockerMetricsService
from app.services.pagination import build_meta, normalize_pagination
from app.simulation.tasks import run_simulation_job

_MAIN_VARIABLES = {"Dispatch", "NewCapacity", "UnmetDemand", "AnnualEmissions"}


class SimulationService:
    """Capa de negocio para gestion de simulaciones."""

    @staticmethod
    def _batch_scenario_tags_by_scenario_ids(db: Session, scenario_ids: set[int]) -> dict[int, dict | None]:
        if not scenario_ids:
            return {}
        rows = db.execute(select(Scenario).where(Scenario.id.in_(scenario_ids))).scalars().all()
        tag_ids = {s.tag_id for s in rows if s.tag_id}
        tags_by_id: dict[int, ScenarioTag] = {}
        if tag_ids:
            for t in db.execute(select(ScenarioTag).where(ScenarioTag.id.in_(tag_ids))).scalars():
                tags_by_id[int(t.id)] = t
        out: dict[int, dict | None] = {}
        for s in rows:
            sid = int(s.id)
            if s.tag_id and s.tag_id in tags_by_id:
                tr = tags_by_id[s.tag_id]
                out[sid] = {
                    "id": int(tr.id),
                    "name": tr.name,
                    "color": tr.color,
                    "sort_order": int(tr.sort_order),
                }
            else:
                out[sid] = None
        return out

    @staticmethod
    def _is_infeasible_succeeded_job(job) -> bool:
        """Corrida técnicamente exitosa pero con modelo infactible o diagnóstico asociado."""
        if getattr(job, "status", None) != "SUCCEEDED":
            return False
        mt = job.model_timings_json or {}
        if not isinstance(mt, dict):
            mt = {}
        ss = str(mt.get("solver_status") or "").lower()
        if "infeasible" in ss or "infactible" in ss:
            return True
        sid = job.infeasibility_diagnostics_json
        if isinstance(sid, dict):
            cv = sid.get("constraint_violations") or []
            vb = sid.get("var_bound_conflicts") or []
            if cv or vb:
                return True
        return False

    @staticmethod
    def _to_public(
        job,
        *,
        queue_position: int | None = None,
        username: str | None = None,
        scenario_name: str | None = None,
        scenario_tag: dict | None = None,
    ) -> dict:
        effective_scenario_name = scenario_name
        if effective_scenario_name is None and getattr(job, "input_mode", "SCENARIO") == "CSV_UPLOAD":
            effective_scenario_name = job.input_name or "CSV upload"

        return {
            "id": job.id,
            "scenario_id": job.scenario_id,
            "scenario_name": effective_scenario_name,
            "scenario_tag": scenario_tag,
            "user_id": str(job.user_id),
            "username": username,
            "solver_name": job.solver_name,
            "input_mode": getattr(job, "input_mode", "SCENARIO"),
            "input_name": getattr(job, "input_name", None),
            "status": job.status,
            "progress": float(job.progress),
            "cancel_requested": bool(job.cancel_requested),
            "queue_position": queue_position,
            "result_ref": job.result_ref,
            "error_message": job.error_message,
            "queued_at": job.queued_at,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "is_infeasible_result": SimulationService._is_infeasible_succeeded_job(job),
        }

    @staticmethod
    def submit(
        db: Session, *, current_user: User, scenario_id: int, solver_name: str = "highs"
    ) -> dict:
        """Encola una nueva simulacion para un escenario autorizado."""
        from app.services.scenario_service import ScenarioService

        try:
            scenario = ScenarioService._require_access(
                db, scenario_id=scenario_id, current_user=current_user
            )
        except ForbiddenError as exc:
            raise ForbiddenError("No tienes acceso al escenario indicado.") from exc

        active_jobs = SimulationRepository.count_user_active_jobs(db, user_id=current_user.id)
        settings = get_settings()
        sync_mode = (
            settings.is_sync_simulation_mode()
            if hasattr(settings, "is_sync_simulation_mode")
            else str(getattr(settings, "simulation_mode", "async")).strip().lower() == "sync"
        )
        if active_jobs >= settings.sim_user_active_limit:
            raise ConflictError(
                f"Ya alcanzaste el maximo de simulaciones activas ({settings.sim_user_active_limit})."
            )

        if solver_name not in {"highs", "glpk"}:
            raise ConflictError("Solver invalido. Usa 'highs' o 'glpk'.")

        job = SimulationRepository.create_job(
            db,
            user_id=current_user.id,
            scenario_id=scenario_id,
            solver_name=solver_name,
            input_mode="SCENARIO",
        )
        # Necesario para obtener `job.id` antes de insertar eventos asociados.
        if hasattr(db, "flush"):
            db.flush()
        SimulationRepository.add_event(
            db,
            job_id=job.id,
            event_type="INFO",
            stage="queue",
            message="Job creado y listo para encolar.",
            progress=0.0,
        )
        db.commit()
        db.refresh(job)

        tag_by_sid = SimulationService._batch_scenario_tags_by_scenario_ids(db, {int(scenario.id)})
        scenario_tag = tag_by_sid.get(int(scenario.id))

        if sync_mode:
            task = run_simulation_job.apply(args=[job.id], throw=False)
            db.refresh(job)
            job.celery_task_id = task.id
            SimulationRepository.add_event(
                db,
                job_id=job.id,
                event_type="INFO",
                stage="queue",
                message="Simulacion ejecutada en modo sincrono local.",
                progress=float(job.progress),
            )
            db.commit()
            db.refresh(job)
            return SimulationService._to_public(
                job,
                queue_position=None,
                username=current_user.username,
                scenario_name=scenario.name,
                scenario_tag=scenario_tag,
            )

        try:
            task = run_simulation_job.delay(job.id)
        except Exception as exc:  # pragma: no cover - depende de broker externo
            db.rollback()
            failed_job = SimulationRepository.get_job_by_id(db, job_id=job.id)
            if failed_job and failed_job.status == "QUEUED":
                failed_job.status = "FAILED"
                failed_job.error_message = f"QUEUE_ENQUEUE_ERROR: {exc}"
                SimulationRepository.add_event(
                    db,
                    job_id=failed_job.id,
                    event_type="ERROR",
                    stage="queue",
                    message=f"No se pudo encolar la simulacion: {exc}",
                    progress=failed_job.progress,
                )
                db.commit()
            raise ConflictError("No se pudo encolar la simulacion. Intenta nuevamente.") from exc

        job.celery_task_id = task.id
        SimulationRepository.add_event(
            db,
            job_id=job.id,
            event_type="INFO",
            stage="queue",
            message="Simulacion encolada.",
            progress=0.0,
        )
        db.commit()
        db.refresh(job)
        return SimulationService._to_public(
            job,
            queue_position=SimulationRepository.queue_position(db, job_id=job.id),
            username=current_user.username,
            scenario_name=scenario.name,
            scenario_tag=scenario_tag,
        )

    @staticmethod
    def submit_from_csv(
        db: Session,
        *,
        current_user: User,
        solver_name: str = "highs",
        input_name: str,
        input_ref: str,
    ) -> dict:
        """Encola una simulación cuyo input proviene de un ZIP de CSV."""
        active_jobs = SimulationRepository.count_user_active_jobs(db, user_id=current_user.id)
        settings = get_settings()
        sync_mode = (
            settings.is_sync_simulation_mode()
            if hasattr(settings, "is_sync_simulation_mode")
            else str(getattr(settings, "simulation_mode", "async")).strip().lower() == "sync"
        )
        if active_jobs >= settings.sim_user_active_limit:
            raise ConflictError(
                f"Ya alcanzaste el maximo de simulaciones activas ({settings.sim_user_active_limit})."
            )

        if solver_name not in {"highs", "glpk"}:
            raise ConflictError("Solver invalido. Usa 'highs' o 'glpk'.")

        job = SimulationRepository.create_job(
            db,
            user_id=current_user.id,
            solver_name=solver_name,
            input_mode="CSV_UPLOAD",
            input_name=input_name,
            input_ref=input_ref,
        )
        if hasattr(db, "flush"):
            db.flush()
        SimulationRepository.add_event(
            db,
            job_id=job.id,
            event_type="INFO",
            stage="queue",
            message="Job CSV creado y listo para encolar.",
            progress=0.0,
        )
        db.commit()
        db.refresh(job)

        if sync_mode:
            task = run_simulation_job.apply(args=[job.id], throw=False)
            db.refresh(job)
            job.celery_task_id = task.id
            SimulationRepository.add_event(
                db,
                job_id=job.id,
                event_type="INFO",
                stage="queue",
                message="Simulacion CSV ejecutada en modo sincrono local.",
                progress=float(job.progress),
            )
            db.commit()
            db.refresh(job)
            return SimulationService._to_public(
                job,
                queue_position=None,
                username=current_user.username,
            )

        try:
            task = run_simulation_job.delay(job.id)
        except Exception as exc:  # pragma: no cover - depende de broker externo
            db.rollback()
            failed_job = SimulationRepository.get_job_by_id(db, job_id=job.id)
            if failed_job and failed_job.status == "QUEUED":
                failed_job.status = "FAILED"
                failed_job.error_message = f"QUEUE_ENQUEUE_ERROR: {exc}"
                SimulationRepository.add_event(
                    db,
                    job_id=failed_job.id,
                    event_type="ERROR",
                    stage="queue",
                    message=f"No se pudo encolar la simulacion CSV: {exc}",
                    progress=failed_job.progress,
                )
                db.commit()
            raise ConflictError("No se pudo encolar la simulacion CSV. Intenta nuevamente.") from exc

        job.celery_task_id = task.id
        SimulationRepository.add_event(
            db,
            job_id=job.id,
            event_type="INFO",
            stage="queue",
            message="Simulacion CSV encolada.",
            progress=0.0,
        )
        db.commit()
        db.refresh(job)
        return SimulationService._to_public(
            job,
            queue_position=SimulationRepository.queue_position(db, job_id=job.id),
            username=current_user.username,
        )

    @staticmethod
    def get_by_id(db: Session, *, current_user: User, job_id: int) -> dict:
        visible = SimulationRepository.get_job_visible(db, job_id=job_id)
        if not visible:
            raise NotFoundError("Simulacion no encontrada.")
        job, username, scenario_name = visible
        queue_position = (
            SimulationRepository.queue_position(db, job_id=job.id) if job.status == "QUEUED" else None
        )
        tags_by_sid = SimulationService._batch_scenario_tags_by_scenario_ids(
            db, {int(job.scenario_id)} if job.scenario_id else set()
        )
        scenario_tag = tags_by_sid.get(int(job.scenario_id)) if job.scenario_id else None
        return SimulationService._to_public(
            job,
            queue_position=queue_position,
            username=username,
            scenario_name=scenario_name,
            scenario_tag=scenario_tag,
        )

    @staticmethod
    def list_jobs(
        db: Session,
        *,
        current_user: User,
        scope: str,
        status: str | None,
        username: str | None,
        scenario_id: int | None,
        solver_name: str | None,
        cantidad: int | None,
        offset: int | None,
    ) -> dict:
        page, page_size, row_offset = normalize_pagination(offset, cantidad)
        normalized_scope = "mine" if scope not in {"mine", "global"} else scope
        items, total = SimulationRepository.list_jobs(
            db,
            scope=normalized_scope,
            user_id=current_user.id,
            status=status,
            username=username,
            scenario_id=scenario_id,
            solver_name=solver_name,
            row_offset=row_offset,
            limit=page_size,
        )
        scenario_ids = {j.scenario_id for j, _, _ in items if j.scenario_id}
        tags_by_sid = SimulationService._batch_scenario_tags_by_scenario_ids(db, {int(x) for x in scenario_ids})
        data = [
            SimulationService._to_public(
                job,
                queue_position=SimulationRepository.queue_position(db, job_id=job.id)
                if job.status == "QUEUED"
                else None,
                username=job_username,
                scenario_name=job_scenario_name,
                scenario_tag=tags_by_sid.get(int(job.scenario_id)) if job.scenario_id else None,
            )
            for job, job_username, job_scenario_name in items
        ]
        meta = build_meta(page, page_size, total, status)
        return {"data": data, "meta": meta}

    @staticmethod
    def cancel(db: Session, *, current_user: User, job_id: int) -> dict:
        job = SimulationRepository.get_job_for_user(db, job_id=job_id, user_id=current_user.id)
        if not job:
            raise NotFoundError("Simulacion no encontrada.")
        if job.status not in ("QUEUED", "RUNNING"):
            raise ConflictError("Solo se pueden cancelar simulaciones en cola o ejecucion.")

        job.cancel_requested = True
        if job.status == "QUEUED":
            job.status = "CANCELLED"
            job.progress = max(job.progress, 0.0)
        SimulationRepository.add_event(
            db,
            job_id=job.id,
            event_type="INFO",
            stage="cancel",
            message="Solicitud de cancelacion registrada.",
            progress=job.progress,
        )
        db.commit()
        db.refresh(job)
        tags_by_sid = SimulationService._batch_scenario_tags_by_scenario_ids(
            db, {int(job.scenario_id)} if job.scenario_id else set()
        )
        scenario_tag = tags_by_sid.get(int(job.scenario_id)) if job.scenario_id else None
        return SimulationService._to_public(job, scenario_tag=scenario_tag)

    @staticmethod
    def list_logs(
        db: Session,
        *,
        current_user: User,
        job_id: int,
        cantidad: int | None,
        offset: int | None,
    ) -> dict:
        visible = SimulationRepository.get_job_visible(db, job_id=job_id)
        if not visible:
            raise NotFoundError("Simulacion no encontrada.")
        job, _, _ = visible
        page, page_size, row_offset = normalize_pagination(offset, cantidad)
        events, total = SimulationRepository.list_events(
            db, job_id=job.id, row_offset=row_offset, limit=page_size
        )
        data = [
            {
                "id": event.id,
                "event_type": event.event_type,
                "stage": event.stage,
                "message": event.message,
                "progress": event.progress,
                "created_at": event.created_at,
            }
            for event in events
        ]
        meta = build_meta(page, page_size, total, None)
        return {"data": data, "meta": meta}

    @staticmethod
    def get_result(db: Session, *, current_user: User, job_id: int) -> dict:
        """Reconstruye el payload RunResult a partir de BD."""
        visible = SimulationRepository.get_job_visible(db, job_id=job_id)
        if not visible:
            raise NotFoundError("Simulacion no encontrada.")
        job, _, _ = visible
        if job.status != "SUCCEEDED":
            raise ConflictError("La simulacion aun no ha finalizado correctamente.")

        rows = (
            db.query(OsemosysOutputParamValue)
            .filter(OsemosysOutputParamValue.id_simulation_job == job.id)
            .all()
        )

        if not rows and job.objective_value is None:
            raise NotFoundError("No se encontraron resultados para esta simulacion.")

        dispatch: list[dict] = []
        new_capacity: list[dict] = []
        unmet_demand: list[dict] = []
        annual_emissions: list[dict] = []
        intermediate_variables: dict[str, list[dict]] = defaultdict(list)

        for r in rows:
            vn = r.variable_name
            if vn == "Dispatch":
                dispatch.append({
                    "region_id": r.id_region or -1,
                    "year": r.year,
                    "technology_name": r.technology_name,
                    "technology_id": r.id_technology or -1,
                    "fuel_name": r.fuel_name,
                    "dispatch": r.value,
                    "cost": r.value2 or 0.0,
                })
            elif vn == "NewCapacity":
                new_capacity.append({
                    "region_id": r.id_region or -1,
                    "technology_id": r.id_technology or -1,
                    "year": r.year,
                    "new_capacity": r.value,
                    "technology_name": r.technology_name,
                })
            elif vn == "UnmetDemand":
                unmet_demand.append({
                    "region_id": r.id_region or -1,
                    "year": r.year,
                    "unmet_demand": r.value,
                })
            elif vn == "AnnualEmissions":
                annual_emissions.append({
                    "region_id": r.id_region or -1,
                    "year": r.year,
                    "annual_emissions": r.value,
                })
            else:
                intermediate_variables[vn].append({
                    "index": r.index_json if r.index_json is not None else [],
                    "value": r.value,
                })

        # Reconstruct sol from main series (frontend may use it)
        sol: dict[str, list[dict]] = {
            "RateOfActivity": [],
            "NewCapacity": [],
            "UnmetDemand": [],
            "AnnualEmissions": [],
        }
        for d in dispatch:
            sol["RateOfActivity"].append({
                "index": [
                    str(d.get("region_id", "")),
                    d.get("technology_name", ""),
                    d.get("fuel_name", ""),
                    d["year"],
                ],
                "value": d["dispatch"],
            })
        for nc in new_capacity:
            sol["NewCapacity"].append({
                "index": [
                    str(nc.get("region_id", "")),
                    nc.get("technology_name", ""),
                    nc["year"],
                ],
                "value": nc["new_capacity"],
            })
        for ud in unmet_demand:
            sol["UnmetDemand"].append({
                "index": [str(ud.get("region_id", "")), ud["year"]],
                "value": ud["unmet_demand"],
            })
        for ae in annual_emissions:
            sol["AnnualEmissions"].append({
                "index": [str(ae.get("region_id", "")), ae["year"]],
                "value": ae["annual_emissions"],
            })

        infeasibility_diagnostics = job.infeasibility_diagnostics_json

        return {
            "job_id": job.id,
            "scenario_id": job.scenario_id,
            "solver_name": job.solver_name,
            "records_used": job.records_used or 0,
            "osemosys_param_records": job.osemosys_param_records or 0,
            "objective_value": job.objective_value or 0.0,
            "solver_status": (job.model_timings_json or {}).get("solver_status", "unknown"),
            "coverage_ratio": job.coverage_ratio or 0.0,
            "total_demand": job.total_demand or 0.0,
            "total_dispatch": job.total_dispatch or 0.0,
            "total_unmet": job.total_unmet or 0.0,
            "dispatch": dispatch,
            "unmet_demand": unmet_demand,
            "new_capacity": new_capacity,
            "annual_emissions": annual_emissions,
            "sol": sol,
            "intermediate_variables": dict(intermediate_variables),
            "osemosys_inputs_summary": job.inputs_summary_json or [],
            "stage_times": job.stage_times_json or {},
            "model_timings": job.model_timings_json or {},
            "infeasibility_diagnostics": infeasibility_diagnostics,
        }

    @staticmethod
    def overview(db: Session, *, current_user: User) -> dict:
        """Resumen operacional global del tablero de simulaciones."""
        services_memory = DockerMetricsService.list_service_memory()
        return {
            **SimulationRepository.count_overview(db),
            "services_memory_total_bytes": sum(item["memory_usage_bytes"] for item in services_memory),
        }
