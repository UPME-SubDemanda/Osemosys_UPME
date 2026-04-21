# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

OSeMOSYS UPME is a web application for running energy scenario optimizations (LP via Pyomo + HiGHS solver) and visualizing results as interactive charts. There are two simulation modes:

- **DB mode** (default): inputs and outputs live in PostgreSQL; no CSV/Excel files are used at runtime.
- **SAND/Excel mode**: simulation launched from an uploaded Excel file, without DB scenario data.

**Stack:**
- Backend: FastAPI + SQLAlchemy + Celery/Redis + Pyomo (`appsi_highs` solver)
- Frontend: React 19 + TypeScript + Vite + Highcharts v11
- DB: PostgreSQL (schemas: `osemosys`, `core`)

---

## Running the Project

### Docker (full stack)

```bash
docker compose up -d --build
docker compose exec api alembic upgrade head
docker compose exec api python scripts/seed.py
# Seed user: seed / seed123
curl http://localhost:8010/api/v1/health
```

### Local without Docker (SQLite, sync mode)

```powershell
.\scripts\setup-local.ps1
.\scripts\init-local-db.ps1
.\scripts\run-local-api.ps1
# Uses backend/.env.local — DATABASE_URL=sqlite:///./tmp/local/osemosys_local.db, SIMULATION_MODE=sync
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Backend tests

```bash
cd backend
pytest                            # all tests
pytest tests/test_visualization_configs.py   # single file
```

### Frontend checks

```bash
cd frontend
npm run typecheck   # tsc --noEmit
npm run lint        # eslint
```

---

## Architecture

### High-level flow

```
User → React frontend
         → FastAPI (app/api/v1/)
              → Celery worker (simulation pipeline)
                   → Pyomo + HiGHS solver
                        → osemosys_output_param_value (PostgreSQL)
              → chart_service.py (reads DB, returns JSON)
         ← Highcharts (renders in browser)
```

### Backend layers

| Layer | Location |
|-------|----------|
| HTTP / routing | `backend/app/api/v1/` |
| Business rules | `backend/app/services/` |
| DB access | `backend/app/models/`, SQLAlchemy ORM |
| Optimization model | `backend/app/simulation/core/` |
| Visualization | `backend/app/visualization/` |

### Simulation pipeline

Entry: `POST /api/v1/simulations` → Celery task → `app/simulation/tasks.py` → `app/simulation/pipeline.py`

**Key modules in `app/simulation/core/`:**

| Module | Role |
|--------|------|
| `data_processing.py` | BD → CSVs (sets + params) OR Excel → CSVs; full pipeline including UDC setup |
| `model_definition.py` | `create_abstract_model(has_storage, has_udc)` — all sets, params, vars, constraints, objective |
| `instance_builder.py` | `build_instance()` — loads CSVs via Pyomo DataPortal, creates ConcreteModel |
| `solver.py` | `solve_model()` — runs HiGHS solver, returns results |
| `results_processing.py` | Extracts solver output → writes to `osemosys_output_param_value` + JSON artefact |
| `excel_to_csv.py` | `generate_csvs_from_excel()` — converts Excel SAND file to CSVs |
| `mode_of_operation_normalize.py` | Normalizes MODE_OF_OPERATION values (scalar + series) |

**Two simulation entry paths in `data_processing.py`:**
- `run_data_processing(db, scenario_id, csv_dir)` — DB path (main flow)
- `run_data_processing_from_excel(excel_path, csv_dir)` — Excel/SAND path (no DB required)

Both paths produce identical CSV structure consumed by `build_instance()`.

Outputs: `osemosys_output_param_value` (PostgreSQL) + JSON artefact at `tmp/simulation-results/simulation_job_<id>.json`.

---

## Chart / Visualization Architecture

This is where most active development happens. See also `backend/app/visualization/README.md`.

### Data flow

```
osemosys_output_param_value (PostgreSQL)
    → chart_service.py  (load → filter → aggregate → convert units → color)
    → FastAPI /visualizations endpoints  (Pydantic JSON)
    → frontend (HighchartsChart.tsx / CompareChart.tsx / CompareChartFacet.tsx / LineChart.tsx)
    → Highcharts charts (stacked bar or line)
```

### Backend visualization module (`backend/app/visualization/`)

| File | Role |
|------|------|
| `chart_service.py` | Core: `build_chart_data`, `build_comparison_data`, `build_comparison_facet_data`, `get_result_summary`, export helpers |
| `configs.py` | Single-scenario chart registry (`CONFIGS` dict, 70+ entries): `variable_default`, `filtro`, `agrupar_por`, `color_fn`, title, flags |
| `configs_comparacion.py` | Multi-scenario comparison registry (`CONFIGS_COMPARACION`): `prefijo`, `agrupacion_*`, `año_historico_unico` |
| `colors.py` | Color logic: `COLORES_GRUPOS`, `FAMILIAS_TEC`, `generar_colores_tecnologias`, `_color_electricidad` |
| `labels.py` | `get_label()` — technology/fuel display names |

### API endpoints (`backend/app/api/v1/visualizations.py`)

| Endpoint | Purpose |
|----------|---------|
| `GET /visualizations/chart-catalog` | Available chart types |
| `GET /visualizations/{job_id}/chart-data?tipo=&un=` | Single-scenario chart |
| `GET /visualizations/chart-data/compare?job_ids=&tipo=&years_to_plot=` | Multi-scenario by year |
| `GET /visualizations/chart-data/compare-facet?job_ids=&tipo=` | Multi-scenario facets |
| `GET /visualizations/{job_id}/result-summary` | KPI header |
| `GET /visualizations/{job_id}/export-chart?tipo=&formato=` | Individual chart export (PNG/SVG/CSV) server-side |
| `GET /visualizations/{job_id}/export-all` | ZIP of SVG/PNG (Matplotlib headless) |
| `GET /visualizations/{job_id}/export-raw` | Excel dump of raw output rows |

All endpoints require authentication; chart-data endpoints require `SUCCEEDED` job status. Comparison is capped at **10 jobs**.

### chart_service internals

`_load_variable_data` has two paths:
- **Typed variables** (`Dispatch`, `NewCapacity`, `UnmetDemand`, `AnnualEmissions`): use typed DB columns directly.
- **Intermediate variables** (everything else): parse `index_json` using position heuristics for 3/4/5-element indices. Malformed indices produce empty/partial charts.

Unit conversion (`_convertir_unidades`): PJ is the baseline. GW, MW, TWh, Gpc apply fixed multipliers.

### Frontend chart components (`frontend/src/shared/charts/`)

| Component | Mode |
|-----------|------|
| `HighchartsChart.tsx` | Single scenario — stacked bar, all years on X-axis |
| `LineChart.tsx` | Single scenario — line chart view mode |
| `CompareChart.tsx` | Multi-scenario by year — one subplot per year, scenarios on X-axis |
| `CompareChartFacet.tsx` | Multi-scenario facets — one complete chart per scenario |
| `ChartSelector.tsx` | Controls: chart type, unit, sub-filter, location, view mode (bar/line) |
| `ScenarioComparer.tsx` | Comparison mode toggle + scenario/year selection |
| `highchartsSetup.ts` | Highcharts global initialization (modules, options) |
| `chartExportingShared.ts` | Shared export utilities (PNG/SVG/CSV) for all chart types |
| `serverChartExport.ts` | Server-side export: calls backend `/export-chart` endpoint |
| `mergeFacetChartsSvg.ts` | Merges individual facet SVGs into a single combined SVG |

The page component `ResultDetailPage.tsx` orchestrates API calls and routes to the correct chart component based on comparison mode and selected view mode (bar vs. line).

### Adding a new single-scenario chart type

1. Add a filter function in `configs.py` (or reuse existing).
2. Add entry to `CONFIGS` with: `variable_default`, `filtro`, `agrupar_por`, `color_fn`, `titulo_base`, `figura_base`, `es_capacidad`, `es_porcentaje`.
3. If the chart supports sub-filters, register in `_config_has_sub_filtro` / `_config_sub_filtros` in `chart_service.py`.

### Adding a new comparison chart type

Add entry to `CONFIGS_COMPARACION` in `configs_comparacion.py` with `prefijo`, `agrupacion_default` or `agrupacion_fija`, `año_historico_unico`, `variable_default`.

### Color rules

Colors are deterministic, keyed by technology family/group. To change a color, edit `colors.py` (`COLORES_GRUPOS` for fuel/sector groups, `COLOR_MAP_PWR` for electricity technologies). Color changes affect all charts using that group.

---

## UDC (User-Defined Constraints)

UDC is an OSeMOSYS extension that lets users define arbitrary linear constraints over technology capacity and activity. This section documents the full UDC pipeline.

### What UDC does

Each UDC constraint `u` has the form:

```
Σ_t [ UDCMultiplierTotalCapacity[r,t,u,y] * TotalCapacity[r,t,y]
    + UDCMultiplierNewCapacity[r,t,u,y]   * NewCapacity[r,t,y]
    + UDCMultiplierActivity[r,t,u,y]      * AnnualActivity[r,t,y] ]
  <= or = UDCConstant[r,u,y]
```

The type of constraint is controlled by `UDCTag[r,u]`:
- `0` → inequality (≤), constraint `UDC1_UserDefinedConstraintInequality`
- `1` → equality (=), constraint `UDC2_UserDefinedConstraintEquality`
- `2` (default) → skip — the constraint is not generated at all

### UDC parameters (model_definition.py)

| Parameter | Dimensions | Default | Description |
|-----------|-----------|---------|-------------|
| `UDCMultiplierTotalCapacity` | `REGION, TECHNOLOGY, UDC, YEAR` | 0 | Coefficient on total installed capacity |
| `UDCMultiplierNewCapacity` | `REGION, TECHNOLOGY, UDC, YEAR` | 0 | Coefficient on new capacity in that year |
| `UDCMultiplierActivity` | `REGION, TECHNOLOGY, UDC, YEAR` | 0 | Coefficient on annual activity |
| `UDCConstant` | `REGION, UDC, YEAR` | 0 | RHS constant of the constraint |
| `UDCTag` | `REGION, UDC` | 2 | Constraint type: 0=≤, 1==, 2=skip |

UDC parameters are only added to the model when `has_udc=True` in `create_abstract_model()`.

### UDC pipeline (data_processing.py)

The UDC pipeline always runs in steps 5–6 of `run_data_processing()`:

**Steps 5–6 — condicional**: Solo se ejecutan si `scenario.udc_config` está configurado y `enabled=True`. Helper `_load_enabled_udc_config(db, scenario_id)` lee el campo y retorna `None` si UDC está deshabilitado o no configurado.

**Step 5 — `ensure_udc_csvs(csv_dir)`**: Hardcodes `udc_list = ["UDC_Margin"]` y genera:
- `UDC.csv` con esa entrada
- `UDCMultiplierTotalCapacity.csv`, `UDCMultiplierNewCapacity.csv`, `UDCMultiplierActivity.csv` (ceros, cross-join con AvailabilityFactor)
- `UDCConstant.csv` (ceros), `UDCTag.csv` (valor 2 = skip por defecto)

**Step 6 — `apply_udc_config(udc_config: dict, csv_dir: str)`**: Recibe el config directamente (ya no lee BD) y llama `actualizar_UDCMultiplier` / `actualizar_UDCTag`. No tiene fallback — si no hay config, no se llama.

### `_UDC_RESERVE_MARGIN_DICT` (hardcoded in data_processing.py)

Dictionary mapping power technology codes to their UDC multiplier for the Reserve Margin constraint. Dispatchable techs get `-1.0` (reduce RHS); non-dispatchable (solar, run-of-river) get `0.0`; grid technology `GRDTYDELC` gets `(1/0.9) * 1.2`. This is the main UDC use case: effectively replacing OSeMOSYS's native Reserve Margin with a UDC formulation.

### `has_udc` detection

`has_udc` se establece en `True` en `ProcessingResult` solo cuando:
1. El escenario tiene `udc_config` configurado con `enabled: True`, y
2. `ensure_udc_csvs` + `apply_udc_config` se ejecutaron exitosamente.

Por defecto (`udc_config=None`) → `has_udc=False` → modelo sin restricciones UDC. En modo Excel/SAND, UDC siempre está deshabilitado (no hay escenario en BD).

### MUIO constraints (model_definition.py lines 1163–1209)

MUIO (LU1–LU4) are defined in the model but currently **not loaded** from CSVs in `instance_builder.py` (commented out). They constrain activity by mode per year (upper/lower bounds, year-over-year increase/decrease rates). To activate them, uncomment the corresponding `_load_param` calls in `instance_builder.py`.

---

## Key Design Decisions

- **Dual simulation path**: DB-mode uses `run_data_processing()` (PostgreSQL → CSVs); SAND/Excel mode uses `run_data_processing_from_excel()` (Excel → CSVs). Both feed the same `build_instance()` → `solve_model()` → `process_results()` pipeline.
- **UDC optional, off by default**: `ensure_udc_csvs()` and `apply_udc_config()` solo se llaman cuando `scenario.udc_config` tiene `"enabled": true`. Nuevos escenarios tienen `udc_config=null` → sin UDC en la simulación.
- **Declarative configs**: Business rules (technology prefixes, sectors, colors) are data in `CONFIGS`/`CONFIGS_COMPARACION`, not scattered in frontend or service code.
- **Two storage shapes**: Primary variables use typed columns; intermediate variables use `index_json` with heuristic parsing.
- **Comparison cap**: Max 10 jobs per comparison to control memory/query cost.
- **Historical year override**: `año_historico_unico=True` in comparison configs makes the first plotted year come from only the first job — for aligned baseline + projection reporting.
- **Visualization labels**: technology and fuel display names are managed in `labels.py` via `get_label()`. There is no external dictionary file — mappings live directly in that module.
- **Individual chart export**: Charts can be exported individually (PNG/SVG/CSV) via a server-side endpoint (`/export-chart`). Frontend uses `serverChartExport.ts` to call this endpoint. Facet export merges SVGs client-side via `mergeFacetChartsSvg.ts`.
- **MODE_OF_OPERATION normalization**: `mode_of_operation_normalize.py` sanitizes mode values before writing CSVs, preventing Pyomo index mismatches from inconsistent input formatting.
