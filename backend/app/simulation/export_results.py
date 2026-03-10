"""Exportar resultados de simulación a carpeta con CSVs (estilo notebook resultados/).

Genera en el directorio indicado:
  - dispatch.csv, new_capacity.csv, unmet_demand.csv, annual_emissions.csv
  - summary.csv (KPIs)
  - simulation_result.json (opcional)
  - Por cada variable intermedia (ProductionByTechnology, UseByTechnology,
    TotalCapacityAnnual, AccumulatedNewCapacity, emisiones, costos, etc.):
    un CSV con columnas de índice + VALUE, para replicar las vistas del notebook.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Nombres de columnas para variables intermedias (alineado con notebook/DataPortal)
# Si la variable tiene exactamente len(columnas) índices, se usan estos nombres en el CSV.
INTERMEDIATE_COLUMN_NAMES: dict[str, list[str]] = {
    "TotalCapacityAnnual": ["REGION", "TECHNOLOGY", "YEAR"],
    "AccumulatedNewCapacity": ["REGION", "TECHNOLOGY", "YEAR"],
    "ProductionByTechnology": ["REGION", "TECHNOLOGY", "FUEL", "DUMMY", "YEAR"],
    "UseByTechnology": ["REGION", "TECHNOLOGY", "FUEL", "DUMMY", "YEAR"],
    "RateOfProductionByTechnology": ["REGION", "TECHNOLOGY", "FUEL", "DUMMY", "YEAR"],
    "RateOfUseByTechnology": ["REGION", "TECHNOLOGY", "FUEL", "DUMMY", "YEAR"],
}


def export_solution_to_folder(
    result: dict,
    output_dir: str | Path,
    *,
    write_json: bool = True,
    use_timestamp_subdir: bool = True,
) -> Path:
    """Escribe los resultados de una corrida OSeMOSYS en una carpeta con CSVs.

    Crea la carpeta si no existe. Por defecto crea una subcarpeta con timestamp
    (run_YYYYMMDD_HHMMSS) dentro de output_dir para no sobrescribir corridas anteriores.

    Parameters
    ----------
    result : dict
        Dict devuelto por run_osemosys_from_db / from_excel / from_csv_dir
        (debe contener dispatch, new_capacity, unmet_demand, annual_emissions,
        objective_value, solver_status, etc.).
    output_dir : str | Path
        Ruta base de resultados (p. ej. resultados/). Si use_timestamp_subdir=True,
        se escribe en output_dir/run_YYYYMMDD_HHMMSS/.
    write_json : bool
        Si True, escribe también simulation_result.json para generate_simulation_charts.
    use_timestamp_subdir : bool
        Si True (default), crea una subcarpeta con fecha y hora para no sobrescribir.
        Si False, escribe directamente en output_dir (sobrescribe archivos).

    Returns
    -------
    Path
        Carpeta donde se escribieron los archivos (puede ser output_dir/run_YYYYMMDD_HHMMSS/).
    """
    base = Path(output_dir).resolve()
    if use_timestamp_subdir:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = base / f"run_{stamp}"
    else:
        out = base
    out.mkdir(parents=True, exist_ok=True)

    # dispatch.csv (process_results ya incluye region_name en cada fila)
    dispatch = result.get("dispatch", [])
    _write_csv(
        out / "dispatch.csv",
        dispatch,
        ["region_id", "region_name", "year", "technology_name", "technology_id", "fuel_name", "dispatch", "cost"],
    )

    # new_capacity.csv
    new_cap = result.get("new_capacity", [])
    _write_csv(
        out / "new_capacity.csv",
        new_cap,
        ["region_id", "region_name", "year", "technology_name", "technology_id", "new_capacity"],
    )

    # unmet_demand.csv
    unmet = result.get("unmet_demand", [])
    _write_csv(out / "unmet_demand.csv", unmet, ["region_id", "region_name", "year", "unmet_demand"])

    # annual_emissions.csv
    emissions = result.get("annual_emissions", [])
    _write_csv(out / "annual_emissions.csv", emissions, ["region_id", "region_name", "year", "annual_emissions"])

    # summary.csv (KPIs)
    summary = [
        {"metric": "objective_value", "value": result.get("objective_value", 0)},
        {"metric": "solver_name", "value": result.get("solver_name", "")},
        {"metric": "solver_status", "value": result.get("solver_status", "")},
        {"metric": "coverage_ratio", "value": result.get("coverage_ratio", 1.0)},
        {"metric": "total_demand", "value": result.get("total_demand", 0)},
        {"metric": "total_dispatch", "value": result.get("total_dispatch", 0)},
        {"metric": "total_unmet", "value": result.get("total_unmet", 0)},
    ]
    _write_csv(out / "summary.csv", summary, ["metric", "value"])

    if write_json:
        # simulation_result.json (estructura esperada por generate_simulation_charts)
        json_path = out / "simulation_result.json"
        payload = {
            "objective_value": result.get("objective_value"),
            "solver_name": result.get("solver_name"),
            "solver_status": result.get("solver_status"),
            "coverage_ratio": result.get("coverage_ratio"),
            "total_demand": result.get("total_demand"),
            "total_dispatch": result.get("total_dispatch"),
            "total_unmet": result.get("total_unmet"),
            "dispatch": result.get("dispatch", []),
            "new_capacity": result.get("new_capacity", []),
            "unmet_demand": result.get("unmet_demand", []),
            "annual_emissions": result.get("annual_emissions", []),
            "sol": result.get("sol", {}),
            "model_timings": result.get("model_timings", {}),
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    # Variables intermedias: un CSV por variable (ProductionByTechnology, UseByTechnology,
    # TotalCapacityAnnual, AccumulatedNewCapacity, emisiones, costos, etc.) — como en el notebook
    intermediate = result.get("intermediate_variables") or {}
    num_intermediate = 0
    for var_name, entries in intermediate.items():
        if not entries or not isinstance(entries, list):
            continue
        # Cada entrada: {"index": [r, t, f, ...], "value": v}
        n_cols = max(len((e.get("index") or [])) for e in entries)
        if n_cols == 0:
            n_cols = 1
        idx_names = INTERMEDIATE_COLUMN_NAMES.get(var_name)
        if idx_names is not None and len(idx_names) == n_cols:
            fieldnames = list(idx_names) + ["VALUE"]
        else:
            fieldnames = [f"IDX{i+1}" for i in range(n_cols)] + ["VALUE"]
        index_keys = fieldnames[:-1]  # todos menos VALUE
        rows = []
        for e in entries:
            idx_vals = e.get("index") or []
            row = {index_keys[i]: idx_vals[i] if i < len(idx_vals) else "" for i in range(n_cols)}
            row["VALUE"] = e.get("value", 0)
            rows.append(row)
        safe_name = _sanitize_filename(var_name)
        _write_csv(out / f"{safe_name}.csv", rows, fieldnames)
        num_intermediate += 1

    logger.info(
        "Resultados exportados a %s (dispatch=%d, new_capacity=%d, %d variables intermedias, summary, json)",
        out, len(dispatch), len(new_cap), num_intermediate,
    )
    return out


def _sanitize_filename(name: str) -> str:
    """Nombre de archivo seguro (sin caracteres que no sean alfanuméricos o _)."""
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in name).strip("_") or "unnamed"


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    import csv
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            # Asegurar que los valores numéricos se escriban como números
            out = {}
            for k in fieldnames:
                v = row.get(k)
                if v is None:
                    out[k] = ""
                else:
                    out[k] = v
            w.writerow(out)
