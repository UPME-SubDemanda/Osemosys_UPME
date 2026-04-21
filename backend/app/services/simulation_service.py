"""Service de negocio para jobs de simulacion."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models import OsemosysOutputParamValue, Scenario, ScenarioTag, User
from app.repositories.simulation_repository import SimulationRepository
from app.services.docker_metrics_service import DockerMetricsService
from app.services.pagination import build_meta, normalize_pagination
from app.simulation.tasks import run_simulation_job

logger = logging.getLogger(__name__)

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
    def _diagnostic_status_for(job) -> tuple[str, str | None]:
        """Devuelve ``(status, error)`` del análisis enriquecido de infactibilidad.

        Ver :func:`_diagnostic_info_for` para el bloque completo (incluye
        timestamps y duración).
        """
        info = SimulationService._diagnostic_info_for(job)
        return info["diagnostic_status"], info["diagnostic_error"]

    @staticmethod
    def _diagnostic_info_for(job) -> dict:
        """Extrae ``status`` + timestamps + duración del diagnóstico desde el JSON."""
        diag = job.infeasibility_diagnostics_json
        out = {
            "diagnostic_status": "NONE",
            "diagnostic_error": None,
            "diagnostic_started_at": None,
            "diagnostic_finished_at": None,
            "diagnostic_seconds": None,
        }
        if not isinstance(diag, dict):
            return out
        raw = diag.get("diagnostic_status")
        if raw in {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED"}:
            out["diagnostic_status"] = raw
        elif diag.get("iis") or diag.get("overview") or diag.get("top_suspects"):
            # Retrocompat: diagnóstico enriquecido ya persistido.
            out["diagnostic_status"] = "SUCCEEDED"
        out["diagnostic_error"] = diag.get("diagnostic_error")
        started = diag.get("diagnostic_started_at")
        finished = diag.get("diagnostic_finished_at")
        if started:
            out["diagnostic_started_at"] = str(started)
        if finished:
            out["diagnostic_finished_at"] = str(finished)
        seconds = diag.get("diagnostic_seconds")
        if isinstance(seconds, (int, float)):
            out["diagnostic_seconds"] = float(seconds)
        return out

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
            "run_iis_analysis": bool(getattr(job, "run_iis_analysis", False)),
            "is_infeasible_result": SimulationService._is_infeasible_succeeded_job(job),
            **SimulationService._diagnostic_info_for(job),
        }

    @staticmethod
    def submit(
        db: Session,
        *,
        current_user: User,
        scenario_id: int,
        solver_name: str = "highs",
        run_iis_analysis: bool = False,
    ) -> dict:
        """Encola una nueva simulacion para un escenario autorizado.

        ``run_iis_analysis`` habilita el análisis enriquecido automático
        (IIS + mapeo a parámetros) cuando el modelo resulta infactible.
        """
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
            run_iis_analysis=run_iis_analysis,
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
        run_iis_analysis: bool = False,
    ) -> dict:
        """Encola una simulación cuyo input proviene de un ZIP de CSV.

        ``run_iis_analysis`` habilita el análisis enriquecido automático
        (IIS + mapeo a parámetros) cuando el modelo resulta infactible.
        """
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
            run_iis_analysis=run_iis_analysis,
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
    def request_infeasibility_diagnostic(
        db: Session,
        *,
        current_user: User,
        job_id: int,
    ) -> dict:
        """Encola el análisis enriquecido de infactibilidad (IIS + mapeo) para
        un job ya completado que resultó infactible.

        Reglas:
            * El job debe existir y pertenecer al usuario (o el usuario tener
              acceso al escenario).
            * Debe estar en ``SUCCEEDED`` y ser infactible.
            * El solver debe ser ``highs`` (GLPK no soporta IIS). Con GLPK se
              devuelve ``ConflictError`` con mensaje explicativo.
            * Si ya hay un diagnóstico en curso (``QUEUED``/``RUNNING``), no
              se re-encola; se devuelve el estado actual.

        El análisis se ejecuta fuera de esta transacción — aquí solo se marca
        ``diagnostic_status='QUEUED'`` y se manda a Celery.
        """
        # Import local para evitar import circular (tasks importa este service).
        from app.simulation.tasks import run_infeasibility_diagnostic_job

        job = SimulationRepository.get_job_for_user(
            db, job_id=job_id, user_id=current_user.id
        )
        if not job:
            raise NotFoundError("Simulación no encontrada.")

        if not SimulationService._is_infeasible_succeeded_job(job):
            raise ConflictError(
                "El diagnóstico solo aplica a simulaciones que terminaron con "
                "estado infactible."
            )

        solver = str(getattr(job, "solver_name", "") or "").lower()
        if solver != "highs":
            raise ConflictError(
                "El diagnóstico de infactibilidad requiere correr la simulación "
                "con HiGHS. Vuelve a lanzar el escenario con HiGHS para habilitar "
                "esta opción."
            )

        current_status, _ = SimulationService._diagnostic_status_for(job)
        if current_status in ("QUEUED", "RUNNING"):
            tags_by_sid = SimulationService._batch_scenario_tags_by_scenario_ids(
                db, {int(job.scenario_id)} if job.scenario_id else set()
            )
            scenario_tag = (
                tags_by_sid.get(int(job.scenario_id)) if job.scenario_id else None
            )
            return SimulationService._to_public(job, scenario_tag=scenario_tag)

        # Marcar como QUEUED antes de encolar Celery.
        diag = dict(job.infeasibility_diagnostics_json or {})
        diag["diagnostic_status"] = "QUEUED"
        diag.pop("diagnostic_error", None)
        job.infeasibility_diagnostics_json = diag
        SimulationRepository.add_event(
            db,
            job_id=job.id,
            event_type="INFO",
            stage="infeasibility_analysis_queue",
            message="Diagnóstico de infactibilidad encolado.",
            progress=job.progress,
        )
        db.commit()
        db.refresh(job)

        # Encolar la task y persistir su task_id (necesario para poder revocar
        # / cancelar desde la UI incluso si aún no inició la ejecución).
        try:
            celery_task = run_infeasibility_diagnostic_job.delay(job.id)
        except Exception as exc:
            # Revertir el estado a NONE para que el usuario pueda reintentar.
            diag["diagnostic_status"] = "FAILED"
            diag["diagnostic_error"] = f"No se pudo encolar la tarea: {exc!r}"
            job.infeasibility_diagnostics_json = diag
            db.commit()
            raise

        diag["diagnostic_celery_task_id"] = celery_task.id
        # Limpiamos cualquier bandera stale de cancelación previa.
        diag.pop("diagnostic_cancel_requested", None)
        job.infeasibility_diagnostics_json = diag
        db.commit()

        tags_by_sid = SimulationService._batch_scenario_tags_by_scenario_ids(
            db, {int(job.scenario_id)} if job.scenario_id else set()
        )
        scenario_tag = (
            tags_by_sid.get(int(job.scenario_id)) if job.scenario_id else None
        )
        return SimulationService._to_public(job, scenario_tag=scenario_tag)

    @staticmethod
    def cancel_infeasibility_diagnostic(
        db: Session,
        *,
        current_user: User,
        job_id: int,
    ) -> dict:
        """Cancela un diagnóstico de infactibilidad en curso o en cola.

        Estrategia en dos partes:

        1. **Marcar la bandera en BD** (``diagnostic_cancel_requested=True``).
           La task Celery la chequea entre fases y aborta limpiamente si la ve.
        2. **Revocar la task en Celery** vía ``celery_app.control.revoke``.
           Si aún está encolada, se descarta antes de iniciar. Si ya está
           corriendo, se envía ``terminate=True`` para matar el worker hijo.
           Esto es útil cuando la task está atrapada dentro de una operación
           Pyomo/HiGHS larga que no llega al siguiente chequeo.

        Respuestas:
            * ``NotFoundError`` si el job no existe / no tiene acceso.
            * ``ConflictError`` si el diagnóstico no está en QUEUED/RUNNING.
        """
        from app.simulation.celery_app import celery_app  # noqa: WPS433

        job = SimulationRepository.get_job_for_user(
            db, job_id=job_id, user_id=current_user.id
        )
        if not job:
            raise NotFoundError("Simulación no encontrada.")

        current_status, _ = SimulationService._diagnostic_status_for(job)
        if current_status not in ("QUEUED", "RUNNING"):
            raise ConflictError(
                "No hay un diagnóstico en curso o en cola para cancelar "
                f"(estado actual: {current_status})."
            )

        diag = dict(job.infeasibility_diagnostics_json or {})
        diag["diagnostic_cancel_requested"] = True
        task_id = diag.get("diagnostic_celery_task_id")

        # Si aún no arrancó (QUEUED), cerramos el ciclo aquí mismo: el worker
        # al tomar la task verá la bandera y la descartará, pero también
        # dejamos el estado en FAILED para que la UI reaccione sin esperar.
        if current_status == "QUEUED":
            diag["diagnostic_status"] = "FAILED"
            diag["diagnostic_finished_at"] = datetime.now(timezone.utc).isoformat()
            diag["diagnostic_error"] = "Cancelado por el usuario antes de iniciar."
            # Los segundos se quedan en 0 porque started_at no se fijó.
            diag["diagnostic_seconds"] = 0.0

        job.infeasibility_diagnostics_json = diag
        SimulationRepository.add_event(
            db,
            job_id=job.id,
            event_type="WARN",
            stage="infeasibility_analysis_cancel",
            message="Cancelación del diagnóstico solicitada por el usuario.",
            progress=job.progress,
        )
        db.commit()
        db.refresh(job)

        # Revocar la task en Celery (best-effort, no bloqueante). Cuando la
        # task está en cola, `revoke` simplemente evita que se despache. Si ya
        # está ejecutándose, `terminate=True` envía SIGTERM al proceso hijo.
        if task_id:
            try:
                celery_app.control.revoke(
                    task_id, terminate=(current_status == "RUNNING"), signal="SIGTERM"
                )
            except Exception:  # pragma: no cover
                logger.warning(
                    "No se pudo revocar la task Celery %s del diagnóstico del job %s",
                    task_id,
                    job_id,
                )

        tags_by_sid = SimulationService._batch_scenario_tags_by_scenario_ids(
            db, {int(job.scenario_id)} if job.scenario_id else set()
        )
        scenario_tag = (
            tags_by_sid.get(int(job.scenario_id)) if job.scenario_id else None
        )
        return SimulationService._to_public(job, scenario_tag=scenario_tag)

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
        # Retrocompat + normalización: si el dict no trae `diagnostic_status`
        # pero ya tiene datos enriquecidos (iis/overview/top_suspects), lo
        # consideramos SUCCEEDED para que el frontend no muestre "aún no
        # ejecutado" sobre un reporte ya completo.
        if isinstance(infeasibility_diagnostics, dict):
            has_status = "diagnostic_status" in infeasibility_diagnostics
            has_enriched_data = bool(
                infeasibility_diagnostics.get("iis")
                or infeasibility_diagnostics.get("overview")
                or infeasibility_diagnostics.get("top_suspects")
                or infeasibility_diagnostics.get("constraint_analyses")
            )
            if not has_status and has_enriched_data:
                infeasibility_diagnostics = {
                    **infeasibility_diagnostics,
                    "diagnostic_status": "SUCCEEDED",
                }

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
