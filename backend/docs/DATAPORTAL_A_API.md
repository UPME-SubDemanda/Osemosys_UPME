# Equivalencia DataPortal (CSV) ↔ API (base de datos)

Este documento mapea el flujo típico de **creación de instancia con DataPortal desde CSV** al flujo de **nuestra API**: los datos vienen de PostgreSQL (`osemosys_param_value` y catálogos) en lugar de archivos CSV; el modelo se arma igual conceptualmente.

## Resumen

| DataPortal (tu script) | Nuestra API |
|------------------------|-------------|
| `DataPortal()` + `data.load(filename=path_csv+"X.csv", set="Y")` | Conjuntos (REGION, TECHNOLOGY, etc.) vienen de catálogos en BD y de los índices usados en `osemosys_param_value` |
| `data.load(filename=path_csv+"X.csv", param="ParamName", index=[...])` | Filas en `osemosys_param_value` con `param_name = "ParamName"` y columnas región, tecnología, combustible, emisión, timeslice, modo, año, UDC, etc. |
| `model.create_instance(data)` | `load_from_db(db, scenario_id)` construye un diccionario de parámetros; `build_context` + `run_model` arman y resuelven el modelo |

Los **nombres de parámetros** en la API se **normalizan** (minúscula, sin caracteres no alfanuméricos). Por ejemplo: `InputActivityRatio` en CSV → `inputactivityratio` en `ctx.params`. En la BD se guarda el nombre tal cual (p. ej. `InputActivityRatio`); el loader lo normaliza al usarlo.

## Conjuntos (sets)

En el script cargas sets desde CSV (EMISSION, FUEL, TIMESLICE, MODE_OF_OPERATION, TECHNOLOGY, YEAR, REGION, STORAGE si aplica, UDC si aplica). En la API:

- **Conjuntos** no se cargan como archivos; se derivan de:
  - Catálogos globales: `region`, `technology`, `fuel`, `emission`, `timeslice`, `mode_of_operation`, etc.
  - Y de las **claves** que aparecen en `osemosys_param_value` para el escenario (regiones, tecnologías, años, etc. que realmente tienen datos).
- Si usas **Almacenamiento**: las dimensiones de almacenamiento se obtienen de filas con `id_storage_set` en `osemosys_param_value` y del catálogo `storage_set`.
- Si usas **UDC**: el set UDC viene del catálogo `udc_set` y de filas con `id_udc_set` en `osemosys_param_value`.

## Carga de parámetros

En el script haces algo como:

```python
data.load(filename=path_csv+"YearSplit.csv", param="YearSplit", index=["TIMESLICE", "YEAR"])
data.load(filename=path_csv+"InputActivityRatio.csv", param="InputActivityRatio", index=["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"])
# ...
if usar_UDC:
    data.load(filename=path_csv+"UDCMultiplierTotalCapacity.csv", param="UDCMultiplierTotalCapacity", index=["REGION", "TECHNOLOGY", "UDC", "YEAR"])
```

En la API:

- Cada fila de parámetro es un registro en **`osemosys_param_value`** (por escenario):
  - `param_name`: nombre del parámetro (ej. `YearSplit`, `InputActivityRatio`, `UDCMultiplierTotalCapacity`).
  - Dimensiones: `id_region`, `id_technology`, `id_fuel`, `id_emission`, `id_timeslice`, `id_mode_of_operation`, `id_season`, `id_daytype`, `id_dailytimebracket`, `id_storage_set`, `id_udc_set`, `year`.
  - `value`: valor numérico.

La **clave** con la que el modelo interno indexa cada valor es la tupla:

`(id_region, id_technology, id_fuel, id_emission, id_timeslice, id_mode_of_operation, id_season, id_daytype, id_dailytimebracket, id_storage_set, id_udc_set, year)`.

- **Cómo llegan los datos a la BD**:
  1. **Importación Excel**: hoja tipo SAND/Parameters (por ejemplo vía `POST /scenarios/import-excel` o importación oficial). El Excel tiene columnas tipo REGION, TECHNOLOGY, FUEL, MODE_OF_OPERATION, YEAR, VALUE (y opcionalmente EMISSION, TIMESLICE, UDC, etc.); el importador escribe en `osemosys_param_value` con el `param_name` que corresponda a cada fila/hoja.
  2. **Valores manuales**: crear/editar valores OSeMOSYS desde la UI o con `POST /scenarios/{id}/osemosys-values` (y similares), usando los mismos nombres de parámetro y dimensiones.

No hace falta “adaptar” el script línea por línea a la API: **ya está adaptado** en el sentido de que la fuente de verdad son las tablas (y catálogos), y el loader lee de ahí y arma la misma estructura lógica que usarías con DataPortal.

## Parámetros que usa el modelo actual de la API

Los bloques del modelo (`constraints_core`, `constraints_emissions`, `constraints_reserve_re`, `constraints_udc`, `objective`, etc.) leen **solo** los parámetros que necesitan. Cualquier otro parámetro que exista en `osemosys_param_value` se carga en `params` pero no se usa aún en restricciones/objetivo. Esta tabla indica **qué nombres normalizados** usa la API (en minúscula, sin espacios):

| Parámetro en tu script (ej.) | Nombre normalizado en API | Uso en modelo |
|------------------------------|----------------------------|----------------|
| ResidualCapacity | residualcapacity | constraints_core, constraints_udc |
| CapacityFactor | capacityfactor | constraints_core |
| AvailabilityFactor | availabilityfactor | constraints_core |
| CapacityToActivityUnit | capacitytoactivityunit | constraints_core |
| TotalAnnualMaxCapacity | totalannualmaxcapacity | constraints_core |
| TotalAnnualMaxCapacityInvestment | totalannualmaxcapacityinvestment | constraints_core |
| CapitalCost | capitalcost | objective |
| FixedCost | fixedcost | objective |
| VariableCost | variablecost | supply_rows / objetivo |
| EmissionsPenalty | emissionspenalty | objective |
| EmissionActivityRatio | emissionactivityratio | constraints_emissions |
| AnnualEmissionLimit | annualemissionlimit | constraints_emissions |
| ReserveMargin | reservemargin | constraints_reserve_re |
| REMinProductionTarget | reminproductiontarget | constraints_reserve_re |
| RETagTechnology | retagtechnology | constraints_reserve_re |
| UDCMultiplierTotalCapacity | udcmultipliertotalcapacity | constraints_udc |
| UDCMultiplierNewCapacity | udcmultipliernewcapacity | constraints_udc |
| UDCMultiplierActivity | udcmultiplieractivity | constraints_udc |
| UDCConstant | udcconstant | constraints_udc |
| UDCTag | udctag | constraints_udc |
| InputActivityRatio / OutputActivityRatio | inputactivityratio, outputactivityratio | supply/demand y lógica de balance (vía supply_rows y parámetros) |

Parámetros que cargas en el script pero que **el modelo actual no usa** (por tanto son opcionales en la BD, para futuras extensiones): por ejemplo YearSplit, DiscountRate, DepreciationMethod, TotalTechnologyAnnualActivityLowerLimit/UpperLimit, TotalTechnologyModelPeriodActivityLowerLimit/UpperLimit, ModelPeriodEmissionLimit, ModelPeriodExogenousEmission, AnnualExogenousEmission, SpecifiedDemandProfile, ReserveMarginTagFuel, RETagFuel, ReserveMarginTagTechnology, TotalAnnualMinCapacityInvestment, TotalAnnualMinCapacity, etc. Puedes guardarlos en `osemosys_param_value` si quieres paridad con el Excel/notebook; no rompen nada.

## Columnas InputActivityRatio / OutputActivityRatio

En tu script reordenas columnas a `REGION, TECHNOLOGY, FUEL, MODE_OF_OPERATION, YEAR, VALUE`. En la API:

- Esas dimensiones se mapean a: región, tecnología, combustible, modo de operación, año (y opcionalmente timeslice, emisión, etc. si lo usas).
- El **preprocesamiento tipo notebook** (que se ejecuta al importar Excel) puede completar matrices y ajustar formatos; los nombres de parámetro deben coincidir con los que espera el modelo (p. ej. `InputActivityRatio`, `OutputActivityRatio`).

## Flujo equivalente en la API

1. **Cargar datos del escenario**  
   - Importar Excel (SAND/Parameters) o importación oficial, **o** crear/actualizar valores OSeMOSYS por API.
2. **Ejecutar simulación**  
   - `POST /simulations` (o el endpoint que dispare el job) con `scenario_id`.  
   - El worker ejecuta: `load_from_db(db, scenario_id)` → `build_context(...)` → `run_model(ctx)` (variables, restricciones, objetivo, solver).  
   - Equivale a tu `model.create_instance(data)` + resolución.

No hace falta un “script DataPortal” separado: la **instancia del modelo** se crea a partir de la BD en cada corrida.

## Procesamiento de la solución del solver (HiGHS / GLPK)

En tu notebook haces dos cosas distintas según el solver:

### HiGHS: leer archivo .sol y convertir a diccionario / DataFrame

- **Tu script**: lee el archivo `.sol` de HiGHS (columnas Index, Status, Lower, Upper, Primal, Dual, Name), parsea los nombres de variables (p. ej. `RateOfActivity(region_tech_fuel_year)`), y construye un diccionario `sol[varname][index_key] = primal`. Luego `sol_variable_to_df(sol, varname, dimnames)` convierte una variable a DataFrame.

- **En la API**: **no se usa archivo .sol**. El solver se ejecuta con Pyomo (`solver.solve(model)`); la solución queda en memoria. Tras el solve, en `model_runner.py` se leen los valores con `pyo.value(model.dispatch[i])`, `pyo.value(model.new_capacity[key])`, etc., y se arma un diccionario de resultados que se devuelve y se persiste.

| Tu script (HiGHS) | API |
|------------------|-----|
| `read_highs_table_solution("solucion_X.sol")` → DataFrame con Name, Primal | No hay archivo .sol; se lee la solución desde el modelo Pyomo en memoria |
| `solution_to_dict_with_sets(instance, df_sol_highs)` → `sol['RateOfActivity']`, etc. | Se extraen variables concretas: `dispatch`, `new_capacity`, `unmet_demand`, `annual_emissions` en listas/dicts con estructura fija |
| `sol_variable_to_df(sol, 'RateOfActivity', dimnames)` → DataFrame | El artefacto del job es JSON con `dispatch`, `new_capacity`, etc.; puedes convertirlo a DataFrame en tu código si descargas el JSON |

**Equivalente en la API:** (1) **Leer solución**: sí; se obtiene de Pyomo tras `solver.solve(model)` y se extrae en `run_model()`. (2) **Estructura por variable**: sí, pero solo para las variables que exponemos: `dispatch`, `new_capacity`, `unmet_demand`, `annual_emissions`. No hay un diccionario genérico `sol[varname]` para cualquier variable. (3) **A DataFrame**: el artefacto del job (JSON) contiene esas listas; puedes descargar el resultado y en Python hacer `pd.DataFrame(solution["dispatch"])`, etc.

**Variables que la API extrae y persiste:** `dispatch`, `new_capacity`, `unmet_demand`, `annual_emissions`, más `objective_value`, `solver_status`, `coverage_ratio`, totales; y en `output_parameter_value` los dispatch por parámetro de entrada.

**Diccionario de solución tipo HiGHS (paridad con el código original):** en el resultado del job y en el artefacto JSON se incluye `sol`, con la misma idea que `solution_to_dict_with_sets`: por cada variable, una lista de `{"index": [region_name, technology_name, fuel_name, year], "value": primal}` (o las dimensiones que correspondan). Variables: `RateOfActivity`, `NewCapacity`, `UnmetDemand`, `AnnualEmissions`. Los índices usan **nombres** (region, technology, fuel) para coincidir con el script original. En Python puedes reconstruir `sol[varname][tuple(index)] = value` a partir de cada lista.

### GLPK: variables intermedias (ProductionByTechnology, TotalCapacityAnnual, UseByTechnology)

- **Tu script**: con GLPK calculas variables derivadas con `value(instance.RateOfActivity[...] * instance.OutputActivityRatio[...])`, etc., y `variable_to_dataframe(variable, index_names)` convierte a DataFrame.

- **En la API**: se calculan variables intermedias tipo GLPK en post-solve y se devuelven en `intermediate_variables`: `TotalCapacityAnnual`, `AccumulatedNewCapacity`, `ProductionByTechnology`, `UseByTechnology`, `RateOfProductionByTechnology`, `RateOfUseByTechnology`. Sin timeslice se usa YearSplit=1; los índices son por nombre (region, technology, fuel, year donde aplique). Se usan parámetros `ResidualCapacity`, `OperationalLife` (por defecto 30 si no existe), `InputActivityRatio`, `OutputActivityRatio`. El artefacto JSON del job incluye `sol` (diccionario de solución por variable) e `intermediate_variables` (listas de `{"index": [...], "value": v}` por variable).

### Resumen solución solver

| Acción en tu script | ¿Existe en la API? |
|---------------------|--------------------|
| Leer solución del solver | Sí; desde Pyomo en memoria (no desde .sol). |
| Extraer variables (dispatch, new_capacity, unmet, emissions) | Sí; en el resultado del job y en el artefacto JSON. |
| Diccionario genérico sol[varname][index] | Parcial; solo variables fijas en formato lista/dict. |
| Convertir variable a DataFrame | No en el backend; sí en tu código usando el JSON del job. |
| Variables intermedias (ProductionByTechnology, UseByTechnology, etc.) | Sí; calculadas en post-solve en `intermediate_variables` (TotalCapacityAnnual, AccumulatedNewCapacity, ProductionByTechnology, UseByTechnology, RateOfProductionByTechnology, RateOfUseByTechnology). |

## Resumen de adaptación

- **Sí, está adaptado a nuestra API**: la misma lógica (sets + parámetros indexados) se obtiene desde PostgreSQL y catálogos.
- **Nombres de parámetros**: los mismos que en tu script (p. ej. InputActivityRatio, ReserveMargin, UDCMultiplierTotalCapacity); en código se usan en minúscula y sin caracteres especiales.
- **Dimensiones**: región, tecnología, combustible, emisión, timeslice, modo, año, UDC (y opcionalmente season, daytype, dailytimebracket, storage) según corresponda a cada parámetro.
- **UDC y almacenamiento**: soportados vía `id_udc_set` / `id_storage_set` y catálogos; el bloque UDC y el de storage los usan cuando hay datos.

Si quieres, el siguiente paso puede ser listar en este mismo doc los parámetros exactos que acepta tu hoja Parameters/SAND en Excel para cruzar 1:1 con `param_name` en la API.
