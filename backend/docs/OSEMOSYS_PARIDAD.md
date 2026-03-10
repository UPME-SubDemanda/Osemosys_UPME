# Paridad OSEMOSYS: Notebook vs Backend

Este documento describe la paridad funcional entre el notebook de referencia
`osemosys_notebook_UPME_OPT_01.ipynb` y la implementación actual de la app
(flujo DB-first).

## Mapeo sección a sección

- **Notebook celdas 4-10 (SAND -> sets/CSV + filtros + matrices)**
  - Importación: `app/services/official_import_service.py`
  - Preproceso tipo notebook en BD: `app/services/sand_notebook_preprocess.py`
  - Exportación BD -> CSV para simulación: `app/simulation/core/data_processing.py`

- **Notebook celda 3 (Model Definition)**
  - `app/simulation/core/model_definition.py`

- **Notebook celda 21 (DataPortal/create_instance)**
  - `app/simulation/core/instance_builder.py`

- **Notebook celda 24 (Solve)**
  - `app/simulation/core/solver.py`

- **Notebook celda 26+ (postproceso/resultados para gráficas)**
  - `app/simulation/core/results_processing.py`
  - Consumo frontend: `frontend/src/pages/ResultDetailPage.tsx`

- **Orquestación de secciones**
  - `app/simulation/osemosys_core.py`
  - `app/simulation/pipeline.py`

## Flujo de ejecución en app

1. Importación Excel (`/official-import/xlsm` o `/scenarios/import-excel`) a `osemosys_param_value`.
2. Preprocesamiento tipo notebook al final de importación (`run_notebook_preprocess`).
3. Simulación (`/simulations`) ejecuta:
   - `run_data_processing` (BD -> CSV temporales),
   - `create_abstract_model`,
   - `build_instance`,
   - `solve_model`,
   - `process_results`.
4. Persistencia de resultado JSON y consumo en frontend (`ResultDetailPage`).

## Invariantes de paridad implementados

- Timeslice agregado a 1 en flujo app (equivalente al notebook con `div=1`).
- Filtrado por sets canónicos para evitar dimensiones fuera de corrida.
- Exclusión de años con `YearSplit=0`.
- Corrección de límites lower/upper invertidos por precisión flotante.
- Carga DataPortal robusta ante CSVs vacíos.
- Dedupe de parámetros por clave de índice antes de crear instancia.

## Pruebas recomendadas de paridad

1. Ejecutar simulación app para escenario(s) de prueba.
2. Exportar JSON de referencia del notebook con:
   - `objective_value`, `coverage_ratio`,
   - `total_demand`, `total_dispatch`, `total_unmet`.
3. Comparar:

```bash
python scripts/compare_results.py --ref tmp/referencia_notebook.json --actual tmp/sand_04_02_2026_result.json --tolerance 1e-6
```

4. Para comparación de tablas completas entre corridas:

```bash
python scripts/run_parity_test.py --tolerance 1e-6
```
