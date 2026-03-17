# Cómo comparar resultados: App vs Jupyter Notebook

Después de ejecutar la misma simulación (mismo Excel, hoja Parameters, solver glpk) en la **app** y en el **notebook**, puedes comparar así.

---

## Dónde está el resultado de la app

- **En la UI:** Simulaciones → fila de la ejecución (ej. ID 12, Escenario 5) → botón **"Abrir"** en la columna **Resultados**. Ahí se abre o descarga el JSON del resultado.
- **En disco (script SAND):** Si usaste `.\scripts\run-sand-test.ps1`, el mismo resultado se copia a `backend/tmp/sand_04_02_2026_result.json` en el host.
- **En el contenedor (por job):** El backend guarda cada resultado en `tmp/simulation-results/simulation_job_{id}.json` (ej. job 12 → `simulation_job_12.json`).

El resultado que ves al hacer clic en **"Abrir"** (ejecución 12, escenario 5) es el mismo que el de `sand_04_02_2026_result.json` si la corrida fue con el mismo escenario SAND_04_02_2026.

---

## 1. Qué tiene el resultado de la app

El archivo `backend/tmp/sand_04_02_2026_result.json` (o el que genere `run-sand-test.ps1`) contiene, entre otras cosas:

| Clave | Significado |
|-------|-------------|
| `objective_value` | Valor de la función objetivo del modelo |
| `total_demand` | Demanda total (suma en el horizonte) |
| `total_dispatch` | Despacho total (generación que cubre la demanda) |
| `total_unmet` | Demanda no cubierta |
| `coverage_ratio` | total_dispatch / total_demand (1.0 = 100 % cubierto) |
| `solver_status` | Estado del solver (p. ej. "optimal") |
| `dispatch` | Tabla detallada por región, año, tecnología (despacho) |
| `new_capacity` | Tabla de nueva capacidad por tecnología y año |
| `unmet_demand` | Tabla de demanda no cubierta por región y año |
| `annual_emissions` | Emisiones anuales por región y año |

---

## 2. Comparación rápida (métricas principales)

### En el notebook Jupyter

Al terminar de resolver el modelo (solver glpk), en el notebook sueles tener algo como:

- **Función objetivo:** `value(model.OBJ)` o similar.
- **Demanda total:** suma de la demanda en el horizonte.
- **Despacho total:** suma del despacho (producción).
- **Demanda no cubierta:** si el modelo la reporta.

Anota estos cuatro números (o cinco si tienes `coverage_ratio`):

- `objective_value`
- `total_demand`
- `total_dispatch`
- `total_unmet`
- `coverage_ratio` (opcional; si no, se puede calcular como total_dispatch / total_demand)

### En la app

Abre `backend/tmp/sand_04_02_2026_result.json` y mira las mismas claves al inicio del JSON:

```json
{
  "objective_value": 126980.25005481177,
  "total_demand": 63490.12500633663,
  "total_dispatch": 126980.25001267325,
  "total_unmet": 0.0,
  "coverage_ratio": 1.0,
  ...
}
```

### Comparar a mano

- Si **objective_value**, **total_demand**, **total_dispatch**, **total_unmet** y **coverage_ratio** son iguales (o casi iguales, p. ej. diferencias en decimales por redondeo), los resultados son equivalentes.
- Si hay diferencias grandes, revisa que en ambos hayas usado: mismo archivo Excel, hoja **Parameters**, mismo solver (**glpk**).

---

## 3. Comparación con el script `compare_last_with_notebook.py` (recomendado)

Desde `backend/` puedes ejecutar:

```powershell
python scripts/compare_last_with_notebook.py
```

- Si **no existe** `tmp/referencia_notebook_sand.json` (ni `referencia_notebook.json`), el script imprime las **métricas del último resultado de la app** para que las compares a mano con el notebook y te indica cómo crear la referencia.
- Si **existe** el archivo de referencia, el script compara automáticamente y devuelve `[OK]` o `[FAIL]`.

El script usa como “último resultado” el más reciente entre `tmp/sand_04_02_2026_result.json`, `tmp/app_result_job*.json` y `tmp/simulation-results/simulation_job_*.json`.

### Paso 1: Crear el JSON de referencia desde el notebook

En el notebook, al final (después de resolver), puedes hacer algo así (ajusta los nombres de variables a tu código):

```python
import json
ref = {
    "objective_value": float(value(model.OBJ)),   # o la variable que tenga el objetivo
    "total_demand": float(tu_suma_demanda),       # suma de demanda en el horizonte
    "total_dispatch": float(tu_suma_despacho),    # suma de despacho/producción
    "total_unmet": float(tu_suma_unmet),          # 0 si todo cubierto
    "coverage_ratio": float(tu_suma_despacho / tu_suma_demanda) if tu_suma_demanda else 0.0
}
with open("referencia_notebook.json", "w") as f:
    json.dump(ref, f, indent=2)
```

Guarda ese archivo en `backend/tmp/referencia_notebook_sand.json` (o `referencia_notebook.json`). Así `compare_last_with_notebook.py` lo detectará solo.

### Paso 2: Ejecutar la comparación

Desde `backend/`:

```powershell
python scripts/compare_last_with_notebook.py
```

O con rutas explícitas:

```powershell
python scripts/compare_results.py --ref tmp/referencia_notebook_sand.json --actual tmp/sand_04_02_2026_result.json --tolerance 1e-4
```

**Salida esperada:**

- Muestra **Métricas de referencia** (las del notebook) y **Métricas actuales** (las de la app).
- Si están dentro de la tolerancia: `[OK] Resultados dentro de la tolerancia.`
- Si no: `[FAIL] Alguna métrica supera la tolerancia.` y puedes ver en qué métricas hay diferencia.

---

## 4. Comparar tablas (opcional)

Si quieres comparar no solo las métricas agregadas sino las tablas:

- **dispatch:** despacho por región, año, tecnología.
- **new_capacity:** nueva capacidad por tecnología y año.
- **unmet_demand:** demanda no cubierta por región y año.
- **annual_emissions:** emisiones por región y año.

El script `compare_results.py` solo compara las cinco métricas anteriores. Para comparar tablas tendrías que:

1. Exportar desde el notebook esas tablas a CSV o JSON (misma estructura que en la app: región, año, tecnología, valor).
2. Comparar a mano o con un script propio (p. ej. pandas: cargar ambos JSON/CSV, merge por claves y restar valores).

Si en el notebook y en la app las **métricas** (objective_value, total_demand, total_dispatch, total_unmet, coverage_ratio) coinciden, es muy probable que las tablas también coincidan, porque esas métricas son agregados de esas tablas.

---

## Resumen

| Qué comparar | Dónde en la app | Cómo |
|--------------|------------------|------|
| Métricas principales | Inicio de `sand_04_02_2026_result.json`: objective_value, total_demand, total_dispatch, total_unmet, coverage_ratio | Anotar los mismos números del notebook y comparar, o usar `compare_results.py` con un JSON de referencia del notebook |
| Tablas detalladas | Arrays `dispatch`, `new_capacity`, `unmet_demand`, `annual_emissions` en el mismo JSON | Exportar desde el notebook a JSON/CSV y comparar por filas (opcional) |

Si las cinco métricas son iguales (o dentro de una tolerancia pequeña, p. ej. 1e-4), puedes considerar que **los resultados de la app y del notebook son equivalentes** para ese mismo input (Excel Parameters, solver glpk).
