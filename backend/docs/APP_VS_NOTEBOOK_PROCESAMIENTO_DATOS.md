# ¿Procesamos bien los datos en la app? Comparación con el notebook

Este documento compara cómo la **app** y el **notebook UPME** cargan y procesan los datos del Excel SAND (hoja Parameters) **antes** de resolver el modelo. Sirve para ver qué hace cada uno y dónde podrían aparecer diferencias.

---

## Resumen ejecutivo

- **Mismo Excel SAND (Parameters) + mismo solver (glpk):** en las pruebas realizadas, las métricas (objective_value, total_demand, total_dispatch, total_unmet, coverage_ratio) coinciden entre app y notebook (comparación con `compare_results.py`).
- La **app no replica** todos los pasos de preprocesamiento del notebook (agregación por `div`, completar matrices con 0, emisiones a la entrada). Usa un **modelo simplificado** y una **importación fila a fila** sin esos tratamientos.
- Para el escenario SAND probado los resultados son equivalentes; en otros escenarios (p. ej. con `div` distinto, o donde las emisiones a la entrada sean relevantes) podría haber diferencias si no se alinean los tratamientos.

---

## 1. Origen de los datos (igual en ambos)

| Aspecto | Notebook | App |
|--------|----------|-----|
| Archivo | Excel SAND (p. ej. `SAND_04_02_2026.xlsm`) | Mismo |
| Hoja | `Parameters` | `Parameters` (vía import oficial o `run_sand_excel_test.py`) |
| Estructura | Columna `Parameter`, columnas de año (2022, 2023, …), columnas de sets (Region, Technology, …) | Misma lectura por filas |

---

## 2. Notebook: pasos antes del modelado

(Detalle en `NOTEBOOK_TRATAMIENTO_DATOS_PRE_OSEMOSYS.md`.)

1. **SAND_SETS_to_CSV:** Extrae sets (REGION, TECHNOLOGY, FUEL, TIMESLICE, YEAR, EMISSION, etc.) desde YearSplit y otros parámetros. Aplica **div** (p. ej. `index % div == 0`) para reducir timeslices (96 → 96/div).
2. **SAND_to_CSV** por cada parámetro:
   - Parámetros con **TIMESLICE:** submuestreo con `div`; **CapacityFactor** se promedia por grupo; otros (p. ej. YearSplit) se agregan por suma.
   - Parámetros sin TIMESLICE: producto (sets × year) → CSV.
3. **Filtrado por sets:** Cada CSV de parámetro se filtra para conservar solo filas cuyos índices (REGION, TECHNOLOGY, …) pertenecen a los sets ya generados.
4. **Completar matrices:** InputActivityRatio, OutputActivityRatio, EmissionActivityRatio, VariableCost (y Storage si aplica) se “completan” con el producto cartesiano de índices y **0** donde no hay valor.
5. **Emisiones a la entrada:** `process_and_save_emission_ratios` actualiza EmissionActivityRatio usando InputActivityRatio (VALUE_emission × VALUE_input).
6. **Carga al modelo:** Pyomo DataPortal carga sets y parámetros desde los CSV ya procesados → modelo abstracto OSeMOSYS completo.

---

## 3. App: qué hace con los datos

### 3.1 Importación (hoja Parameters)

- **Dónde:** `OfficialImportService._import_sand_matrix_sheet` en `app/services/official_import_service.py`.
- **Qué hace:**
  - Recorre el Excel **fila a fila**.
  - Por cada fila lee: `Parameter`, `Region`, `Technology`, `Fuel`, `Emission`, `Timeslice`, `Mode_of_operation`, `Storage`, columnas de año (cabeceras 1900–2200) y opcionalmente `Time indipendent variables`.
  - Crea/obtiene IDs de catálogo (Region, Technology, Fuel, etc.) con `_get_or_create_*` según lo que aparezca en la fila.
  - Escribe en `osemosys_param_value`:
    - Una fila por columna **año** con valor **solo si `abs(year_value) > 0`** (las celdas en 0 no se guardan).
    - Una fila por **Time indipendent variables** si existe y es no nula.

**Qué no hace la app en la importación:**

| Paso del notebook | ¿Lo hace la app? |
|-------------------|------------------|
| Reducir timeslices con **div** (submuestreo) | No. Lee todas las filas tal cual. |
| Agregar CapacityFactor (media) o YearSplit (suma) por grupo | No. |
| Filtrar parámetros por pertenencia a sets predefinidos | No. Los sets se construyen al vuelo con lo que aparece en la hoja. |
| **Completar matrices** (rellenar con 0 todas las combinaciones) | No. Solo persiste valores no nulos. |
| **process_and_save_emission_ratios** (emisión por combustible de entrada) | No. EmissionActivityRatio queda como en el Excel. |

### 3.2 Carga para el modelo (parameters_loader)

- **Dónde:** `load_from_db` en `app/simulation/core/parameters_loader.py`.
- **Qué hace:**
  - Lee `parameter_value` y `osemosys_param_value` del escenario.
  - Construye `demand_rows`, `supply_rows` y un diccionario `params` (nombre de parámetro normalizado → clave → valor).
  - Si faltan filas de oferta para (region, technology, year), genera filas “sintéticas” a partir de parámetros como OutputActivityRatio, InputActivityRatio, CapacityFactor, ResidualCapacity, etc.
  - Asigna costos variables desde `params["variablecost"]` o un proxy por (region, year).

El modelo de la app es **simplificado** (sets SUPPLY, DEMAND_KEY, TECH_KEY; variables dispatch, unmet, new_capacity, annual_emissions), no el OSeMOSYS abstracto completo. Los parámetros se usan en restricciones y objetivo según este esquema reducido.

### 3.3 Emisiones en la app

- **Dónde:** `constraints_emissions.py`.
- **Qué hace:** Agrega EmissionActivityRatio por (region, technology, year) tomando el **máximo** sobre los índices (emisión, modo, etc.) y usa ese valor en la restricción de emisiones anuales.
- **Nota:** No se aplica el paso del notebook que mezcla EmissionActivityRatio con InputActivityRatio; en la app se usa el valor “crudo” del Excel (o de la BD).

---

## 4. Tabla resumen: ¿paridad de procesamiento?

| Tratamiento | Notebook | App | ¿Puede afectar resultados? |
|-------------|----------|-----|----------------------------|
| Lectura Excel Parameters | Sí, por parámetro → CSV | Sí, fila a fila → BD | No (misma fuente). |
| div / reducción de timeslices | Sí (96/div) | No | Solo si en el notebook usas div > 1; entonces el notebook agrega, la app no. |
| Filtrado por sets | Sí (solo índices en sets) | No (sets = lo que aparece) | Posible si el Excel tiene filas “fuera de set” que el notebook elimina. |
| Completar matrices con 0 | Sí | No | En Pyomo los params suelen tener default 0; puede haber diferencias si el modelo usa explícitamente “solo índices presentes”. |
| Emisión a la entrada (Emission × Input) | Sí (process_and_save_emission_ratios) | No | Sí en escenarios donde ese ajuste cambie mucho los factores. |
| Modelo | OSeMOSYS completo (DataPortal) | Modelo simplificado (supply/demand, dispatch, capacity, emissions) | La formulación es distinta; para el SAND probado las métricas coinciden. |

---

## 5. Paridad exacta implementada en la app

La app aplica por defecto (al importar hoja Parameters / SAND) el preprocesamiento tipo notebook: sets canónicos, filtrado por sets, completar matrices (InputActivityRatio, OutputActivityRatio, EmissionActivityRatio, VariableCost) y emisiones a la entrada. Módulo `app/services/sand_notebook_preprocess.py`; opción `notebook_parity=True` en `import_xlsm` y en POST `/official-import/xlsm`. Div/reducción de timeslices no implementado.

- **Para el caso probado (SAND_04_02_2026, glpk):** Sí, en la práctica. Las métricas comparadas (objective_value, total_demand, total_dispatch, total_unmet, coverage_ratio) coinciden; por tanto la combinación importación + modelo simplificado está reproduciendo bien ese resultado.
- **En general:** Con `notebook_parity=True` (por defecto) ya se aplican filtrado por sets, completar matrices y emisiones a la entrada. Si en el notebook usas **div** > 1 (reducción de timeslices), eso aún no está implementado. Mientras no uses `div`, no dependas de “filas fuera de set” y las emisiones a la entrada no cambien mucho el EmissionActivityRatio, es esperable que los resultados sigan siendo muy parecidos.

Recomendación: seguir usando `compare_results.py` al cambiar de escenario o de Excel para comprobar que las métricas sigan dentro de la tolerancia esperada.
