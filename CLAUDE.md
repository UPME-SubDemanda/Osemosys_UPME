# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

OSeMOSYS UPME is a web application for running energy scenario optimizations (LP via Pyomo + HiGHS solver) and visualizing results as interactive charts. The system is fully DB-first: all inputs and outputs live in PostgreSQL; no CSV/Excel files are used at runtime.

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

Entry: `POST /api/v1/simulations` → Celery task → `app/simulation/pipeline.py`

Key modules in `app/simulation/core/`:
- `parameters_loader.py` — loads DB rows into Pyomo-ready structures
- `sets_and_indices.py` / `variables.py` — model structure
- `constraints_*.py` — LP constraint blocks (core, emissions, reserve/RE, storage, UDC)
- `objective.py` — cost minimization + penalty terms
- `model_runner.py` — runs solver, extracts results

Outputs are written to `osemosys_output_param_value` and a JSON artefact at `tmp/simulation-results/simulation_job_<id>.json`.

---

## Chart / Visualization Architecture

This is where most active development happens. See also `backend/app/visualization/README.md`.

### Data flow

```
osemosys_output_param_value (PostgreSQL)
    → chart_service.py  (load → filter → aggregate → convert units → color)
    → FastAPI /visualizations endpoints  (Pydantic JSON)
    → frontend (HighchartsChart.tsx / CompareChart.tsx / CompareChartFacet.tsx)
    → Highcharts stacked bar charts
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
| `CompareChart.tsx` | Multi-scenario by year — one subplot per year, scenarios on X-axis |
| `CompareChartFacet.tsx` | Multi-scenario facets — one complete chart per scenario |
| `ChartSelector.tsx` | Controls: chart type, unit, sub-filter, location |
| `ScenarioComparer.tsx` | Comparison mode toggle + scenario/year selection |

The page component `ResultDetailPage.tsx` orchestrates API calls and routes to the correct chart component based on comparison mode.

### Adding a new single-scenario chart type

1. Add a filter function in `configs.py` (or reuse existing).
2. Add entry to `CONFIGS` with: `variable_default`, `filtro`, `agrupar_por`, `color_fn`, `titulo_base`, `figura_base`, `es_capacidad`, `es_porcentaje`.
3. If the chart supports sub-filters, register in `_config_has_sub_filtro` / `_config_sub_filtros` in `chart_service.py`.

### Adding a new comparison chart type

Add entry to `CONFIGS_COMPARACION` in `configs_comparacion.py` with `prefijo`, `agrupacion_default` or `agrupacion_fija`, `año_historico_unico`, `variable_default`.

### Color rules

Colors are deterministic, keyed by technology family/group. To change a color, edit `colors.py` (`COLORES_GRUPOS` for fuel/sector groups, `COLOR_MAP_PWR` for electricity technologies). Color changes affect all charts using that group.

---

## Key Design Decisions

- **DB-centric**: No CSV/file dependencies at runtime; all data from PostgreSQL.
- **Declarative configs**: Business rules (technology prefixes, sectors, colors) are data in `CONFIGS`/`CONFIGS_COMPARACION`, not scattered in frontend or service code.
- **Two storage shapes**: Primary variables use typed columns; intermediate variables use `index_json` with heuristic parsing.
- **Comparison cap**: Max 10 jobs per comparison to control memory/query cost.
- **Historical year override**: `año_historico_unico=True` in comparison configs makes the first plotted year come from only the first job — for aligned baseline + projection reporting.
- **Visualization labels**: technology and fuel display names are managed in `labels.py` via `get_label()`. There is no external dictionary file — mappings live directly in that module.
