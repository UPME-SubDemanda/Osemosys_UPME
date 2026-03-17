# Tratamiento de datos en el notebook UPME antes del modelado OSeMOSYS

Este documento resume cómo el notebook `osemosys_notebook_UPME_OPT_01.ipynb` carga, transforma y prepara los datos **antes** de crear la instancia del modelo OSeMOSYS y resolverlo.

---

## 1. Origen de los datos

- **Archivo:** Excel SAND (p. ej. `./SAND/SAND_04_02_2026.xlsm` o `SAND_26_03_2025_UPME_almacenamiento.xlsm`).
- **Hoja:** `Parameters`.
- **Variable:** `df_colombia = pd.read_excel(..., sheet_name='Parameters')`.
- **Configuración:** `path_csv = "./CSV/"`, `div` (divisiones temporales, p. ej. 1 o 2; 96/div para timeslices).

---

## 2. Flujo general

```
Excel SAND (hoja Parameters)
    → SAND_SETS_to_CSV (genera sets + algunos parámetros base)
    → SAND_to_CSV por cada parámetro (genera CSV por parámetro)
    → Filtrado por índices válidos (solo valores que pertenecen a los sets)
    → Completar matrices (InputActivityRatio, OutputActivityRatio, etc.)
    → Procesamiento de emisiones (EmissionActivityRatio con InputActivityRatio)
    → [Opcional] Escenarios (Carbononeutralidad: límites de emisión, UDC, etc.)
    → Reordenar columnas de Activity Ratios
    → DataPortal: data.load(...) de sets y parámetros desde CSV
    → model.create_instance(data) → solver
```

---

## 3. SAND_SETS_to_CSV(df, path_csv, div)

- **Entrada:** `df` = DataFrame de la hoja Parameters.
- **Qué hace:**
  - Usa **YearSplit** para inferir años y sets: filtra filas con `index % div == 0` para reducir timeslices.
  - Genera CSV de **sets** a partir de columnas no numéricas (REGION, TECHNOLOGY, FUEL, TIMESLICE, etc.) y **YEAR.csv** con los años.
  - A partir de **EmissionActivityRatio** extrae los valores únicos de **EMISSION** y escribe `EMISSION.csv`.
  - A partir de **OutputActivityRatio** vuelve a extraer y escribir sets (TECHNOLOGY, FUEL, etc.).
  - A partir de **CapacityToActivityUnit** (variables “Time independent”) extrae sets y escribe TECHNOLOGY, REGION, etc.
- **Salida:** Archivos en `path_csv`: `YEAR.csv`, `REGION.csv`, `TECHNOLOGY.csv`, `FUEL.csv`, `TIMESLICE.csv`, `EMISSION.csv`, etc.

---

## 4. SAND_to_CSV(df, param, path_csv, div)

Convierte cada **parámetro** del Excel SAND en un CSV con columnas (sets + YEAR + VALUE).

- **Filtro:** `df_param = df[df["Parameter"] == param].dropna(axis=1)`.
- **Años:** columnas numéricas del DataFrame.
- **Sets:** columnas no numéricas (salvo 'Parameter').

**Casos tratados:**

1. **"Time indipendent variables"**  
   Una sola columna de valor. Se renombra a `VALUE` y se guarda el CSV sin índice temporal explícito por año (o con estructura fija según el parámetro).

2. **Parámetros con TIMESLICE (dependientes del tiempo intranual)**  
   - Se submuestrea con `df_param.index % div == 0` para agrupar timeslices (reducción de resolución).
   - **CapacityFactor:** se promedian los bloques por grupo (`groupby('index_col').mean()`) y se reasignan por año; luego se genera el producto (sets × year) y se escribe VALUE.
   - **Resto (p. ej. YearSplit):** se eliminan filas con todo cero, se agregan por grupo (`sum`), se asigna por año y se genera el producto (sets × year) → CSV con columnas sets + YEAR + VALUE.
   - Resultado: CSV con todas las combinaciones (sets, YEAR) y VALUE.

3. **Parámetros sin TIMESLICE**  
   Se indexa por `sets`, se hace el producto cartesiano con `year`, se rellena VALUE desde `df_param_indexed` y se guarda `{param}.csv` con columnas sets + YEAR + VALUE. Se hace `dropna(axis=1)` al final.

- **Salida:** `path_csv/{param}.csv` (p. ej. `CapacityFactor.csv`, `SpecifiedAnnualDemand.csv`).

---

## 5. Filtrado por índices válidos

Después de generar todos los parámetros:

- Para cada parámetro se lee su CSV.
- Para cada columna de “set” (REGION, TECHNOLOGY, FUEL, etc., salvo VALUE y REGION2 si aplica) se carga el CSV del set correspondiente (p. ej. `TECHNOLOGY.csv`).
- Se filtran las filas del parámetro de modo que cada índice pertenezca al set:  
  `df_prueba[s].isin(df_sets.VALUE.tolist())`.
- Se sobrescribe el CSV del parámetro con este DataFrame filtrado.

Con esto se eliminan combinaciones (r, t, f, …) que no pertenecen a los conjuntos definidos en el modelo.

---

## 6. Completar matrices (relleno de celdas faltantes)

Las matrices de ratios y costos se “completan” para que existan **todas** las combinaciones (REGION, TECHNOLOGY, MODE, …) con VALUE definido (0 donde no había dato).

- **completar_Matrix_Act_Ratio(variable)**  
  - Para `InputActivityRatio.csv` y `OutputActivityRatio.csv`.
  - Producto cartesiano: REGION × TECHNOLOGY × MODE_OF_OPERATION × FUEL × YEAR (regiones del CSV; TECHNOLOGY, MODE, FUEL, YEAR desde sus CSV).
  - Merge con el CSV existente (how='left'), VALUE faltante → 0, se guarda el CSV.

- **completar_Matrix_Emission(variable)**  
  - Para `EmissionActivityRatio.csv`.
  - Producto: REGION × TECHNOLOGY × EMISSION × MODE_OF_OPERATION × YEAR.
  - Merge left, fillna(0) en VALUE, se guarda.

- **completar_Matrix_Storage(variable)**  
  - Solo si `Correr == "Almacenamiento"`.
  - Para `TechnologyFromStorage.csv` y `TechnologyToStorage.csv`.
  - Producto: REGION × TECHNOLOGY × STORAGE × MODE_OF_OPERATION.
  - Mismo esquema: merge, 0 donde falte, guardar.

- **completar_Matrix_Cost(variable)**  
  - Para `VariableCost.csv`.
  - Producto: REGION × TECHNOLOGY × MODE_OF_OPERATION × YEAR.
  - Merge left, VALUE faltante = 0, guardar.

Así Pyomo recibe parámetros definidos en todos los índices del modelo (evita huecos en los índices).

---

## 7. Procesamiento de emisiones (entrada de combustible)

- **process_and_save_emission_ratios(emission_activity_path, input_activity_path, output_path)**  
  - Lee `EmissionActivityRatio` e `InputActivityRatio`.
  - Merge por REGION, TECHNOLOGY, MODE_OF_OPERATION, YEAR.
  - Filtra filas con VALUE_x != 0 y VALUE_y != 0.
  - Calcula `VALUE = VALUE_x * VALUE_y` (emisión por uso de combustible en la entrada).
  - Agrupa por (REGION, TECHNOLOGY, EMISSION, MODE_OF_OPERATION, YEAR), mantiene un valor.
  - Actualiza el DataFrame de EmissionActivityRatio con estos valores (donde corresponda) y guarda en `output_path` (típicamente sobrescribe `EmissionActivityRatio.csv`).

Con esto se contabilizan emisiones asociadas al **input** de combustible (no solo a la actividad directa).

---

## 8. Escenarios (opcional)

- **Escenario == "Carbononeutralidad"**  
  - Se genera una serie lineal de límites de emisión (p. ej. de 90 a 30 entre 2024 y 2050).
  - **emissions_limit(emission_limit_path, df_new):** actualiza el CSV de límite anual (AnnualEmissionLimit) con la nueva serie por año.
  - Se crean/actualizan archivos UDC (restricciones definidas por el usuario): `UDC.csv`, `UDCMultiplierTotalCapacity`, `UDCMultiplierNewCapacity`, `UDCMultiplierActivity`, `UDCConstant`, `UDCTag`, a partir de AvailabilityFactor, REGION, YEAR, etc.

- **UDC (User Defined Constraints)**  
  - Si `usar_UDC == True` se crean los CSV de UDC (listas de UDC, multiplicadores por capacidad/actividad, constante y tag ≤/＝).

---

## 9. Último paso antes de DataPortal

- Se reordenan columnas de `InputActivityRatio.csv` y `OutputActivityRatio.csv` a:  
  `['REGION', 'TECHNOLOGY', 'FUEL', 'MODE_OF_OPERATION', 'YEAR', 'VALUE']`  
  y se guardan de nuevo.
- A continuación se usa **Pyomo DataPortal**: `data.load(filename=path_csv+..., set=...)` o `param=..., index=[...]` para cargar sets y parámetros desde los CSV ya tratados.

---

## 10. Resumen para paridad app vs notebook

Para que la app reproduzca los mismos resultados que el notebook:

1. **Misma fuente:** misma hoja (Parameters) y mismo Excel SAND (o equivalente).
2. **Misma lógica SAND → CSV:**  
   - Misma identificación de años y sets.  
   - Mismo `div` y mismo submuestreo (index % div == 0) en parámetros con TIMESLICE.  
   - Misma regla para CapacityFactor (media) vs otros (suma) en agregación por grupo.
3. **Mismo filtrado:** eliminar filas de parámetros cuyos índices no estén en los sets.
4. **Mismas matrices completadas:** InputActivityRatio, OutputActivityRatio, EmissionActivityRatio, VariableCost (y Storage si aplica) con producto cartesiano y relleno con 0.
5. **Mismo procesamiento de emisiones:** process_and_save_emission_ratios con InputActivityRatio para actualizar EmissionActivityRatio.
6. **Misma carga en el modelo:** mismos CSV (o mismos datos en memoria) y mismos índices en `data.load(...)`.

Referencia de comparación numérica: `backend/docs/COMPARAR_RESULTADOS_APP_VS_NOTEBOOK.md` y script `backend/scripts/compare_results.py`.
