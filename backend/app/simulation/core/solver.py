"""Resolución del modelo OSeMOSYS.

Replica las celdas 27-28 del notebook OPT_YA_20260220:
  - Generación de archivo LP con symbolic_solver_labels (opcional)
  - SolverFactory("glpk").solve(instance) o appsi_highs
  - Diagnósticos de infactibilidad (constraint violations, variable bounds)

Uso: recibe la instancia concreta de instance_builder.build_instance();
     devuelve dict con solver_name, solver_status, objective_value.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pyomo.environ as pyo
from pyomo.core import Constraint, Var, value

logger = logging.getLogger(__name__)

# Alias usado en solve_model -> nombre del factory Pyomo (appsi_highs, glpk).
SOLVER_FACTORIES: dict[str, str] = {"highs": "appsi_highs", "glpk": "glpk"}


def get_solver_availability() -> dict[str, bool]:
    """Comprueba para cada solver si está disponible (instalado y usable)."""
    availability: dict[str, bool] = {}
    for solver_alias, solver_factory in SOLVER_FACTORIES.items():
        solver = pyo.SolverFactory(solver_factory)
        availability[solver_alias] = bool(
            solver is not None and solver.available(exception_flag=False)
        )
    return availability


def write_lp_file(
    instance: pyo.ConcreteModel,
    lp_path: str | Path,
) -> Path:
    """Genera archivo LP con etiquetas simbólicas para debugging.

    Replica la celda 27 del notebook OPT_YA_20260220.
    symbolic_solver_labels=True hace que los nombres de restricciones/variables sean legibles.
    """
    lp_path = Path(lp_path)
    lp_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Generando archivo LP: %s", lp_path)
    instance.write(
        filename=str(lp_path),
        io_options={"symbolic_solver_labels": True},
    )
    file_size_mb = lp_path.stat().st_size / (1024 * 1024)
    logger.info("Archivo LP generado (%.2f MB): %s", file_size_mb, lp_path)
    return lp_path


def _run_infeasibility_diagnostics(instance: pyo.ConcreteModel) -> dict:
    """Analiza restricciones violadas y variable bounds conflictivos.

    Replica la lógica de diagnósticos de infactibilidad de la celda 28
    del notebook OPT_YA_20260220.
    - Recorre restricciones activas: si body < lower o body > upper (con tol 1e-6), registra violación.
    - Recorre variables: si lb > ub, registra conflicto de bounds.
    - Escribe en log las peores 10 y recomendaciones de debugging.
    - Retorna dict con listas estructuradas para persistencia y exportación.
    """
    tol = 1e-6

    logger.warning("=" * 70)
    logger.warning("MODELO INFACTIBLE - ANÁLISIS DIAGNÓSTICO")
    logger.warning("=" * 70)

    constraint_violations_raw: list[tuple[str, float, float | None, float | None, str, float]] = []
    for con in instance.component_data_objects(Constraint, active=True):
        body_val = value(con.body, exception=False)
        if body_val is None:
            continue

        lb = value(con.lower, exception=False) if con.has_lb() else None
        ub = value(con.upper, exception=False) if con.has_ub() else None

        violation = 0.0
        bound_side = ""
        if lb is not None and body_val < lb - tol:
            violation = lb - body_val
            bound_side = "LB"
        elif ub is not None and body_val > ub + tol:
            violation = body_val - ub
            bound_side = "UB"

        if violation > tol:
            constraint_violations_raw.append(
                (con.name, body_val, lb, ub, bound_side, violation)
            )

    constraint_violations_raw.sort(key=lambda x: -x[5])

    if constraint_violations_raw:
        logger.warning(
            "Encontradas %d restricciones violadas", len(constraint_violations_raw),
        )
        for idx, (name, body_val, lb, ub, side, vio) in enumerate(
            constraint_violations_raw[:10]
        ):
            lb_txt = f"{lb:.2e}" if lb is not None else "-inf"
            ub_txt = f"{ub:.2e}" if ub is not None else "+inf"
            logger.warning(
                "  %d. %s: Body=%.6e, Bounds=[%s, %s], Violated=%s, Violation=%.2e",
                idx + 1, name, body_val, lb_txt, ub_txt, side, vio,
            )
    else:
        logger.warning(
            "No se detectaron violaciones explícitas de restricciones; "
            "la infactibilidad puede deberse a bounds conflictivos de variables"
        )

    var_bound_conflicts_raw: list[tuple[str, float, float, float]] = []
    for var in instance.component_data_objects(Var, active=True):
        lb = value(var.lb, exception=False) if var.has_lb() else None
        ub = value(var.ub, exception=False) if var.has_ub() else None
        if lb is not None and ub is not None and lb > ub + tol:
            var_bound_conflicts_raw.append((var.name, lb, ub, lb - ub))

    var_bound_conflicts_raw.sort(key=lambda x: -x[3])

    if var_bound_conflicts_raw:
        logger.warning(
            "Encontradas %d variables con bounds infactibles (LB > UB):",
            len(var_bound_conflicts_raw),
        )
        for idx, (name, lb, ub, gap) in enumerate(var_bound_conflicts_raw[:10]):
            logger.warning(
                "  %d. %s: LB=%.2e, UB=%.2e, Gap=%.2e",
                idx + 1, name, lb, ub, gap,
            )
    else:
        logger.warning("Todos los bounds de variables son consistentes (LB <= UB)")

    logger.warning("RECOMENDACIONES DE DEBUGGING:")
    logger.warning("  1. Verificar restricciones de demanda vs capacidad disponible")
    logger.warning("  2. Verificar ResidualCapacity y upper bounds no sean restrictivos")
    logger.warning("  3. Inspeccionar InputActivityRatio/OutputActivityRatio")
    logger.warning("  4. Confirmar consistencia de unidades entre fuels, actividades y capacidades")
    logger.warning("  5. Revisar balance energético: todos los fuels deben tener rutas de suministro")
    logger.warning("  6. Verificar datos de matrices (CapacityFactor, ActivityRatios)")
    logger.warning("=" * 70)

    return {
        "constraint_violations": [
            {
                "name": name,
                "body": body_val,
                "lower": lb,
                "upper": ub,
                "side": side,
                "violation": vio,
            }
            for name, body_val, lb, ub, side, vio in constraint_violations_raw
        ],
        "var_bound_conflicts": [
            {"name": name, "lb": lb, "ub": ub, "gap": gap}
            for name, lb, ub, gap in var_bound_conflicts_raw
        ],
    }


def solve_model(
    instance: pyo.ConcreteModel,
    *,
    solver_name: str = "glpk",
    lp_path: str | Path | None = None,
) -> dict:
    """Resuelve el modelo usando Pyomo SolverFactory.

    Replica las celdas 27-28 del notebook OPT_YA_20260220.
    - Si lp_path no es None, escribe el .lp antes de resolver.
    - Prueba primero el solver solicitado; si no está disponible, prueba el otro (highs/glpk).
    - Si el status es infactible, ejecuta _run_infeasibility_diagnostics.
    - Retorna dict con solver_name, solver_status, objective_value y,
      si infactible, infeasibility_diagnostics.
    """
    if lp_path is not None:
        write_lp_file(instance, lp_path)

    solver_availability = get_solver_availability()

    # Orden de intento: el solicitado primero, luego el resto.
    fallback_order = (
        [solver_name, *[n for n in SOLVER_FACTORIES if n != solver_name]]
        if solver_name in SOLVER_FACTORIES
        else list(SOLVER_FACTORIES.keys())
    )

    for candidate in fallback_order:
        factory_name = SOLVER_FACTORIES.get(candidate)
        if not factory_name or not solver_availability.get(candidate, False):
            continue

        logger.info("Resolviendo con %s (SolverFactory('%s'))...", candidate, factory_name)
        solver = pyo.SolverFactory(factory_name)
        results = solver.solve(instance, tee=True, keepfiles=True)

        status = str(results.solver.termination_condition)
        obj = 0.0
        try:
            obj = float(pyo.value(instance.OBJ))
        except Exception:
            pass

        logger.info("Solver %s terminó: status=%s, objective=%.4f", candidate, status, obj)

        diagnostics: dict | None = None
        if "infeasible" in status.lower():
            diagnostics = _run_infeasibility_diagnostics(instance)
        elif "optimal" in status.lower():
            logger.info("SOLUCIÓN ÓPTIMA ENCONTRADA - Objetivo: %.2f", obj)

        return {
            "solver_name": candidate,
            "solver_status": status,
            "objective_value": obj,
            "infeasibility_diagnostics": diagnostics,
        }

    # Ningún solver estaba disponible.
    avail_text = ", ".join(
        f"{n}={'ok' if e else 'missing'}" for n, e in solver_availability.items()
    )
    raise RuntimeError(
        f"No hay solvers disponibles. Solicitado: '{solver_name}'. "
        f"Disponibilidad: {avail_text}."
    )
