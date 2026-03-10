"""Procesamiento de resultados post-solve.

Replica la celda 26 del notebook: extracción de variables,
cálculo de variables intermedias, y construcción del dict
de resultados compatible con el pipeline.

Entrada: instancia resuelta + solver_result (de solver.solve_model) + lookups (region_id_by_name, etc.).
Salida: dict con objective_value, coverage_ratio, dispatch, new_capacity, unmet_demand,
        annual_emissions, sol (RateOfActivity, NewCapacity, UnmetDemand, AnnualEmissions),
        intermediate_variables, model_timings.
"""

from __future__ import annotations

import logging
from collections import defaultdict

import pandas as pd
import pyomo.environ as pyo

logger = logging.getLogger(__name__)


def _coerce_year(value) -> int | None:
    """Convierte valores de año (str/int/float) a int de forma robusta."""
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _coerce_number(value, default: float = 0.0) -> float:
    """Convierte un valor a float; usa default si no es convertible."""
    if value is None:
        return default
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return default
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def _safe_extract(var_component) -> dict:
    """Extrae valores de un componente Pyomo (Param/Var); sustituye None por 0.0."""
    raw = var_component.extract_values()
    return {k: (v if v is not None else 0.0) for k, v in raw.items()}


def _variable_to_dataframe(variable, index_names: list[str] | None = None) -> pd.DataFrame:
    """Convierte variable Pyomo indexada o dict a DataFrame.

    Replica la función variable_to_dataframe del notebook.
    Si variable es dict, las claves son tuplas (índices) y el valor el número.
    """
    rows = []

    if isinstance(variable, dict):
        first_key = next(iter(variable))
        n_indices = len(first_key) if isinstance(first_key, tuple) else 1
        if index_names is None:
            columns = [f"IDX{i+1}" for i in range(n_indices)] + ["VALUE"]
        else:
            columns = list(index_names) + ["VALUE"]

        for k, v in variable.items():
            if n_indices == 1:
                rows.append((k, v))
            else:
                rows.append((*k, v))
    else:
        first_idx = next(iter(variable))
        n_indices = len(first_idx) if isinstance(first_idx, tuple) else 1
        if index_names is None:
            columns = [f"IDX{i+1}" for i in range(n_indices)] + ["VALUE"]
        else:
            columns = list(index_names) + ["VALUE"]

        for idx in variable:
            v = variable[idx].value
            if n_indices == 1:
                rows.append((idx, v))
            else:
                rows.append((*idx, v))

    return pd.DataFrame(rows, columns=columns)


# ========================================================================
#  Extracción de resultados principales
# ========================================================================

def _extract_dispatch(
    instance: pyo.ConcreteModel,
    region_id_by_name: dict[str, int],
    technology_id_by_name: dict[str, int],
) -> list[dict]:
    """Extrae dispatch: actividad anual por (región, tecnología, año).
    Usa RateOfActivity × YearSplit para actividad por timeslice; suma por año.
    Asigna coste variable medio y el fuel 'principal' (OutputActivityRatio > 0) por (r,t,y).
    """
    roa_raw = _safe_extract(instance.RateOfActivity)

    ys_param = getattr(instance, "YearSplit", None)
    ys_data: dict = {}
    if ys_param is not None:
        ys_data = _safe_extract(ys_param) if hasattr(ys_param, "extract_values") else {}

    oar_param = getattr(instance, "OutputActivityRatio", None)
    oar_data: dict = {}
    if oar_param is not None:
        oar_data = _safe_extract(oar_param) if hasattr(oar_param, "extract_values") else {}

    vc_param = getattr(instance, "VariableCost", None)
    vc_data: dict = {}
    if vc_param is not None:
        vc_data = _safe_extract(vc_param) if hasattr(vc_param, "extract_values") else {}

    activity_by_rty: dict[tuple, float] = defaultdict(float)
    cost_by_rty: dict[tuple, float] = defaultdict(float)

    for (r, l, t, mo, y), roa in roa_raw.items():
        if abs(roa) < 1e-10:
            continue
        ys = ys_data.get((l, y), 1.0) if ys_data else 1.0
        act = roa * ys
        activity_by_rty[(r, t, y)] += act
        vc = vc_data.get((r, t, mo, y), 0.0) if vc_data else 0.0
        cost_by_rty[(r, t, y)] += act * vc

    # Best fuel per (r, t, y)
    best_fuel: dict[tuple, str] = {}
    for (r, t, f, mo, y), oar_val in oar_data.items():
        if oar_val > 0:
            key = (r, t, y)
            if key not in best_fuel:
                best_fuel[key] = f

    results = []
    for (r, t, y), total_act in activity_by_rty.items():
        if total_act < 1e-10:
            continue
        avg_cost = cost_by_rty[(r, t, y)] / total_act if total_act > 0 else 0.0
        results.append({
            "region_id": region_id_by_name.get(r, -1),
            "year": _coerce_year(y),
            "technology_name": t,
            "technology_id": technology_id_by_name.get(t, -1),
            "fuel_name": best_fuel.get((r, t, y)),
            "dispatch": total_act,
            "cost": avg_cost,
        })
    return results


def _extract_new_capacity(
    instance: pyo.ConcreteModel,
    region_id_by_name: dict[str, int],
    technology_id_by_name: dict[str, int],
) -> list[dict]:
    """Lista de dicts con region_id, technology_id, year, new_capacity, technology_name."""
    nc_raw = _safe_extract(instance.NewCapacity)
    return [
        {
            "region_id": region_id_by_name.get(k[0], -1),
            "technology_id": technology_id_by_name.get(k[1], -1),
            "year": _coerce_year(k[2]),
            "new_capacity": v,
            "technology_name": k[1],
        }
        for k, v in nc_raw.items()
    ]


def _index_ratio_by_rtmoy(
    ratio_data: dict[tuple, float],
) -> dict[tuple, list[tuple[str, float]]]:
    """Pre-indexa OAR/IAR: {(r,t,mo,y) -> [(fuel, value), ...]} para lookup O(1)."""
    idx: dict[tuple, list[tuple[str, float]]] = defaultdict(list)
    for (r, t, f, mo, y), val in ratio_data.items():
        if val > 0:
            idx[(r, t, mo, y)].append((f, val))
    return idx


def _compute_unmet_demand(
    instance: pyo.ConcreteModel,
    region_id_by_name: dict[str, int],
) -> list[dict]:
    """Demanda insatisfecha = max(0, Demand - Production) por (r, fuel, y).
    Producción por fuel viene de RateOfActivity × OutputActivityRatio × YearSplit;
    demanda de Demand (param). Se agrega por (r, y) para el listado final.
    """
    roa_raw = _safe_extract(instance.RateOfActivity)

    ys_param = getattr(instance, "YearSplit", None)
    ys_data = _safe_extract(ys_param) if ys_param and hasattr(ys_param, "extract_values") else {}

    oar_param = getattr(instance, "OutputActivityRatio", None)
    oar_data = _safe_extract(oar_param) if oar_param and hasattr(oar_param, "extract_values") else {}
    oar_idx = _index_ratio_by_rtmoy(oar_data)

    demand_param = getattr(instance, "Demand", None)
    demand_data = _safe_extract(demand_param) if demand_param and hasattr(demand_param, "extract_values") else {}

    prod_by_rfy: dict[tuple, float] = defaultdict(float)
    for (r, l, t, mo, y), roa in roa_raw.items():
        if abs(roa) < 1e-10:
            continue
        ys = ys_data.get((l, y), 1.0)
        for f, oar_val in oar_idx.get((r, t, mo, y), ()):
            prod_by_rfy[(r, f, y)] += roa * oar_val * ys

    demand_by_rfy: dict[tuple, float] = defaultdict(float)
    for (r, l, f, y), dval in demand_data.items():
        demand_by_rfy[(r, f, y)] += dval

    unmet_by_ry: dict[tuple, float] = defaultdict(float)
    for (r, f, y), total_demand in demand_by_rfy.items():
        total_prod = prod_by_rfy.get((r, f, y), 0.0)
        gap = max(0.0, total_demand - total_prod)
        unmet_by_ry[(r, y)] += gap

    return [
        {
            "region_id": region_id_by_name.get(r, -1),
            "year": _coerce_year(y),
            "unmet_demand": v,
        }
        for (r, y), v in sorted(unmet_by_ry.items())
    ]


def _extract_annual_emissions(
    instance: pyo.ConcreteModel,
    region_id_by_name: dict[str, int],
    regions: list,
    years: list,
    emissions: list,
) -> list[dict]:
    """Extrae AnnualEmissions por (región, año); si no hay emisiones, devuelve 0.0 por (r,y)."""
    if not emissions:
        return [
            {
                "region_id": region_id_by_name.get(r, -1),
                "year": _coerce_year(y),
                "annual_emissions": 0.0,
            }
            for r in regions for y in years
        ]

    ae_raw = _safe_extract(instance.AnnualEmissions)
    totals: dict[tuple, float] = defaultdict(float)
    for (r, e, y), v in ae_raw.items():
        totals[(r, y)] += v

    return [
        {
            "region_id": region_id_by_name.get(r, -1),
            "year": _coerce_year(y),
            "annual_emissions": totals.get((r, y), 0.0),
        }
        for r in regions for y in years
    ]


# ========================================================================
#  Variables intermedias (celda 26 del notebook)
# ========================================================================

def _compute_intermediate_variables(
    instance: pyo.ConcreteModel,
    regions: list,
    technologies: list,
    years: list,
    emissions: list,
    has_storage: bool,
) -> dict[str, list]:
    """Calcula variables intermedias para reportes: TotalCapacityAnnual, AccumulatedNewCapacity,
    ProductionByTechnology, UseByTechnology, RateOfProduction/Use, emisiones por tecnología,
    costos descontados, salvage; si has_storage, variables de almacenamiento.
    Cada entrada es lista de {"index": [...], "value": float}.
    """
    out: dict[str, list] = {}

    nc_raw = _safe_extract(instance.NewCapacity)

    ol_param = getattr(instance, "OperationalLife", None)
    ol_data = _safe_extract(ol_param) if ol_param and hasattr(ol_param, "extract_values") else {}

    rc_param = getattr(instance, "ResidualCapacity", None)
    rc_data = _safe_extract(rc_param) if rc_param and hasattr(rc_param, "extract_values") else {}

    year_pairs = []
    for y in years:
        y_num = _coerce_year(y)
        if y_num is None:
            continue
        year_pairs.append((y, int(y_num)))

    # TotalCapacityAnnual + AccumulatedNewCapacity
    tca_entries = []
    anc_entries = []
    for r in regions:
        for t in technologies:
            ol = int(_coerce_number(ol_data.get((r, t), 1), default=1.0))
            if ol <= 0:
                ol = 1
            for y, y_num in year_pairs:
                acc = sum(
                    nc_raw.get((r, t, yy), 0.0)
                    for yy, yy_num in year_pairs
                    if 0 <= (int(y_num) - int(yy_num)) < ol
                )
                res = rc_data.get((r, t, y), 0.0)
                tca_entries.append({"index": [r, t, y_num], "value": acc + res})
                anc_entries.append({"index": [r, t, y_num], "value": acc})
    out["TotalCapacityAnnual"] = tca_entries
    out["AccumulatedNewCapacity"] = anc_entries

    # ProductionByTechnology y UseByTechnology via RateOfActivity
    roa_raw = _safe_extract(instance.RateOfActivity)

    ys_param = getattr(instance, "YearSplit", None)
    ys_data = _safe_extract(ys_param) if ys_param and hasattr(ys_param, "extract_values") else {}

    oar_param = getattr(instance, "OutputActivityRatio", None)
    oar_data = _safe_extract(oar_param) if oar_param and hasattr(oar_param, "extract_values") else {}
    oar_idx = _index_ratio_by_rtmoy(oar_data)

    iar_param = getattr(instance, "InputActivityRatio", None)
    iar_data = _safe_extract(iar_param) if iar_param and hasattr(iar_param, "extract_values") else {}
    iar_idx = _index_ratio_by_rtmoy(iar_data)

    prod_by_rtfy: dict[tuple, float] = defaultdict(float)
    use_by_rtfy: dict[tuple, float] = defaultdict(float)

    for (r, l, t, mo, y), roa in roa_raw.items():
        if abs(roa) < 1e-10:
            continue
        ys = ys_data.get((l, y), 1.0)
        for f, oar_val in oar_idx.get((r, t, mo, y), ()):
            prod_by_rtfy[(r, t, f, y)] += roa * oar_val * ys
        for f, iar_val in iar_idx.get((r, t, mo, y), ()):
            use_by_rtfy[(r, t, f, y)] += roa * iar_val * ys

    out["ProductionByTechnology"] = [
        {"index": [r, t, f, "", _coerce_year(y)], "value": v}
        for (r, t, f, y), v in prod_by_rtfy.items() if v > 1e-10
    ]
    out["UseByTechnology"] = [
        {"index": [r, t, f, "", _coerce_year(y)], "value": v}
        for (r, t, f, y), v in use_by_rtfy.items() if v > 1e-10
    ]
    out["RateOfProductionByTechnology"] = out["ProductionByTechnology"]
    out["RateOfUseByTechnology"] = out["UseByTechnology"]

    # Emissions variables
    if emissions:
        for var_name in ("AnnualTechnologyEmission",
                         "AnnualTechnologyEmissionPenaltyByEmission"):
            pyo_var = getattr(instance, var_name, None)
            if pyo_var is None:
                continue
            vals = _safe_extract(pyo_var)
            entries = [
                {"index": list(k), "value": v}
                for k, v in vals.items() if abs(v) > 1e-10
            ]
            if entries:
                out[var_name] = entries

    # Cost / salvage variables
    for var_name in ("DiscountedOperatingCost", "DiscountedCapitalInvestment",
                     "SalvageValue", "DiscountedSalvageValue"):
        pyo_var = getattr(instance, var_name, None)
        if pyo_var is None:
            continue
        vals = _safe_extract(pyo_var)
        entries = [
            {"index": list(k), "value": v}
            for k, v in vals.items() if abs(v) > 1e-10
        ]
        if entries:
            out[var_name] = entries

    # Storage variables
    if has_storage:
        for var_name in (
            "StorageUpperLimit", "StorageLowerLimit",
            "StorageLevelYearStart", "StorageLevelYearFinish",
            "SalvageValueStorage", "DiscountedSalvageValueStorage",
            "TotalDiscountedStorageCost", "NewStorageCapacity",
            "CapitalInvestmentStorage", "AccumulatedNewStorageCapacity",
        ):
            pyo_var = getattr(instance, var_name, None)
            if pyo_var is None:
                continue
            vals = _safe_extract(pyo_var)
            entries = [{"index": list(k), "value": v} for k, v in vals.items()]
            if entries:
                out[var_name] = entries

    return out


# ========================================================================
#  Pipeline principal de resultados
# ========================================================================

def process_results(
    instance: pyo.ConcreteModel,
    solver_result: dict,
    *,
    regions: list,
    technologies: list,
    years: list,
    emissions: list,
    has_storage: bool,
    region_id_by_name: dict[str, int],
    technology_id_by_name: dict[str, int],
    region_name_by_id: dict[int, str],
) -> dict:
    """Construye el dict de resultados compatible con el pipeline.

    Retorna la misma estructura que el run_model() anterior.
    Pasos: extrae dispatch, new_capacity, unmet_demand, annual_emissions; calcula coverage_ratio
    y total_demand; construye sol (listas con index + value); calcula intermediate_variables y timings.
    """
    from time import perf_counter
    timings: dict[str, float] = {}

    t = perf_counter()
    normalized_years = []
    for y in years:
        y_num = _coerce_year(y)
        if y_num is not None:
            normalized_years.append(y_num)

    dispatch = _extract_dispatch(instance, region_id_by_name, technology_id_by_name)
    new_capacity = _extract_new_capacity(instance, region_id_by_name, technology_id_by_name)
    unmet = _compute_unmet_demand(instance, region_id_by_name)
    annual_emissions = _extract_annual_emissions(
        instance, region_id_by_name, regions, normalized_years, emissions,
    )
    timings["extract_results_seconds"] = perf_counter() - t

    # Añadir region_name a cada fila para exportación a CSV (resultados/)
    for row in dispatch:
        row["region_name"] = region_name_by_id.get(row["region_id"], "")
    for row in new_capacity:
        row["region_name"] = region_name_by_id.get(row["region_id"], "")
    for row in unmet:
        row["region_name"] = region_name_by_id.get(row["region_id"], "")
    for row in annual_emissions:
        row["region_name"] = region_name_by_id.get(row["region_id"], "")

    t = perf_counter()
    total_dispatch = sum(row["dispatch"] for row in dispatch)
    total_unmet = sum(row["unmet_demand"] for row in unmet)

    sad_param = getattr(instance, "SpecifiedAnnualDemand", None)
    sad_data = _safe_extract(sad_param) if sad_param and hasattr(sad_param, "extract_values") else {}
    aad_param = getattr(instance, "AccumulatedAnnualDemand", None)
    aad_data = _safe_extract(aad_param) if aad_param and hasattr(aad_param, "extract_values") else {}
    total_demand = sum(sad_data.values()) + sum(aad_data.values())

    coverage_ratio = 1.0
    if total_demand > 0:
        coverage_ratio = max(0.0, min(1.0, (total_demand - total_unmet) / total_demand))

    # Build sol dict
    sol: dict[str, list] = {
        "RateOfActivity": [],
        "NewCapacity": [],
        "UnmetDemand": [],
        "AnnualEmissions": [],
    }
    for row in dispatch:
        sol["RateOfActivity"].append({
            "index": [
                region_name_by_id.get(row["region_id"], ""),
                row.get("technology_name", ""),
                row.get("fuel_name", ""),
                row["year"],
            ],
            "value": row["dispatch"],
        })
    for row in new_capacity:
        sol["NewCapacity"].append({
            "index": [
                region_name_by_id.get(row["region_id"], ""),
                row.get("technology_name", ""),
                row["year"],
            ],
            "value": row["new_capacity"],
        })
    for row in unmet:
        sol["UnmetDemand"].append({
            "index": [region_name_by_id.get(row["region_id"], ""), row["year"]],
            "value": row["unmet_demand"],
        })
    for row in annual_emissions:
        sol["AnnualEmissions"].append({
            "index": [region_name_by_id.get(row["region_id"], ""), row["year"]],
            "value": row["annual_emissions"],
        })

    intermediate_variables = _compute_intermediate_variables(
        instance, regions, technologies, normalized_years, emissions, has_storage,
    )
    timings["intermediate_vars_seconds"] = perf_counter() - t

    return {
        "objective_value": solver_result["objective_value"],
        "solver_name": solver_result["solver_name"],
        "solver_status": solver_result["solver_status"],
        "coverage_ratio": coverage_ratio,
        "total_demand": total_demand,
        "total_dispatch": total_dispatch,
        "total_unmet": total_unmet,
        "dispatch": dispatch,
        "unmet_demand": unmet,
        "new_capacity": new_capacity,
        "annual_emissions": annual_emissions,
        "sol": sol,
        "intermediate_variables": intermediate_variables,
        "model_timings": timings,
    }
