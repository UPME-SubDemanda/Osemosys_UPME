# Arquitectura Técnica (C4 + Motor OSEMOSYS)

Este documento complementa `README.md` y sirve como referencia de arquitectura para mantenimiento, evolución y operación del backend.

## 1) Vista de Contexto (C4 - System Context)

El sistema backend OSEMOSYS se integra con:

- **Usuarios técnicos/analistas** que gestionan escenarios y ejecutan simulaciones.
- **Frontend web** que consume API REST para escenarios, jobs, progreso y resultados.
- **PostgreSQL** como fuente de verdad de insumos/modelo y estado de ejecución.
- **Redis + Celery** para cola y ejecución asíncrona de optimizaciones.
- **Solver LP/MILP** (HiGHS vía Pyomo) para resolver el problema matemático.

## 2) Vista de Contenedores (C4 - Container)

Contenedores lógicos:

- **API FastAPI**
  - Entrada HTTP.
  - Capa de aplicación (routers, services, repositories).
  - Publica endpoints de negocio y simulación.
- **Worker Celery**
  - Consume jobs de Redis.
  - Ejecuta pipeline de simulación y escribe artefactos.
- **PostgreSQL**
  - Schemas `core` y `osemosys`.
  - Persistencia transaccional de catálogo, escenarios, parámetros, jobs y eventos.
- **Redis**
  - Broker/backend de Celery.

Flujo alto nivel:

1. `POST /simulations` crea `simulation_job` en `QUEUED`.
2. Worker toma job y avanza `RUNNING` -> `SUCCEEDED/FAILED/CANCELLED`.
3. API expone estado, logs y resultados (`/result`).

## 3) Vista de Componentes (C4 - Component)

### 3.1 API Layer

- `app/main.py`: app factory + CORS + registro de routers.
- `app/api/v1/api.py`: composición de endpoints v1.
- `app/api/v1/simulations.py`: endpoint de submit/status/list/cancel/logs/result.

### 3.2 Application/Domain Layer

- `app/services/simulation_service.py`
  - Permisos por escenario.
  - Límite de jobs activos por usuario.
  - Traducción de entidades a contrato público.
  - Resolución de artefacto final.

### 3.3 Data Access Layer

- `app/repositories/simulation_repository.py`
  - CRUD de jobs/eventos.
  - `queue_position`.
  - conteos de jobs activos.

### 3.4 Simulation Engine Layer

- `app/simulation/celery_app.py`: inicialización Celery.
- `app/simulation/tasks.py`: task principal del job.
- `app/simulation/pipeline.py`: orquestación por etapas, cancelación cooperativa y artefactos.
- `app/simulation/osemosys_core.py`: fachada DB-first.
- `app/simulation/core/*`: bloques matemáticos Pyomo.

## 4) Mapa de Módulos del Motor OSEMOSYS

### 4.1 Ingesta y normalización

- `core/parameters_loader.py`
  - Lee `parameter_value` + `osemosys_param_value`.
  - Normaliza nombres de parámetros.
  - Construye `DemandRow`, `SupplyRow` y mapas de parámetros.

### 4.2 Construcción de contexto

- `core/sets_and_indices.py`
  - Genera índices de demanda/oferta/tecnología.
  - Construye `ModelContext`.

### 4.3 Modelo matemático

- `core/variables.py`
  - Variables principales (`dispatch`, `unmet`, `new_capacity`) y auxiliares.
- `core/constraints_core.py`
  - Balance, capacidad, límites de inversión/capacidad.
- `core/constraints_emissions.py`
  - Emisiones agregadas y límite anual.
- `core/constraints_reserve_re.py`
  - Reserve margin + RE target con variables de gap.
- `core/constraints_storage.py`
  - Bloque storage (proxy actual).
- `core/constraints_udc.py`
  - Bloque UDC (proxy actual).
- `core/objective.py`
  - Función objetivo de costo total con penalizaciones.
- `core/model_runner.py`
  - Ensambla modelo, ejecuta solver y extrae resultados.

## 5) Flujos Operacionales Críticos

### 5.1 Submit de simulación

1. API valida acceso al escenario.
2. Verifica límite por usuario (`SIM_USER_ACTIVE_LIMIT`).
3. Crea job y encola task Celery.
4. Registra evento inicial en `simulation_job_event`.

### 5.2 Ejecución worker

1. Task marca job en `RUNNING`.
2. Pipeline ejecuta etapas:
   - `extract_data`
   - `build_model`
   - `solve`
   - `persist_results`
3. Persiste artefacto JSON y `result_ref`.
4. Marca job final y registra evento terminal.

### 5.3 Cancelación cooperativa

- `cancel_requested` se evalúa entre etapas y sub-etapas.
- Si se activa, finaliza en `CANCELLED` sin continuar solve/persistencia.

## 6) Contratos de Resultado

Artefacto estándar (`/result`) incluye:

- KPI principales: `objective_value`, `coverage_ratio`, `total_demand`, `total_dispatch`, `total_unmet`.
- Series:
  - `dispatch`
  - `unmet_demand`
  - `new_capacity`
  - `annual_emissions`
- Metadatos:
  - `stage_times`
  - `model_timings`
  - `solver_status`

## 7) Decisiones Arquitectónicas Relevantes

- **DB-first**: evita archivos CSV/Excel en runtime y centraliza gobernanza de datos.
- **Asíncrono por cola**: desacopla latencia de solve del request HTTP.
- **Bloques de modelo**: facilita extensión gradual y revisión de formulación.
- **Artefacto JSON**: trazabilidad y consumo directo por frontend.

## 8) Riesgos Técnicos Actuales

- Storage/UDC en implementación proxy (no formulación completa canónica).
- Dependencia de calidad semántica en `param_name` para carga de parámetros.
- Tuning solver limitado a defaults.
- Escalamiento sujeto a capacidad de CPU/RAM del host on-prem.

## 9) Guía de Cambio Seguro

Antes de modificar restricciones/objetivo:

1. Crear rama de trabajo.
2. Cambiar únicamente bloque objetivo (`core/constraints_*.py` o `core/objective.py`).
3. Ejecutar validaciones:
   - compilación de backend;
   - corrida de benchmark;
   - `scripts/validate_simulation_parity.py`.
4. Documentar impacto en:
   - factibilidad;
   - objetivo;
   - tiempos de solve.

## 10) Roadmap de Arquitectura

- Separar motor de optimización a microservicio dedicado.
- Incorporar telemetría de rendimiento por bloque y por tamaño de instancia.
- Parametrizar solver por escenario (tiempo límite, tolerancias, estrategia).
- Completar paridad matemática de bloques storage y UDC.
- Incorporar validaciones semánticas fuertes para ingesta de parámetros.
