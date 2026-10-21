# Migración del SAND PD de 2 TS a 6 TS

**Estado (19-oct-2026):** caso de 6 TS construido, factible y verificado. Archivo entregable: `tmp/sand/outputs/PD_6TS_41D_2055_SAND_19Oct2026.xlsx`.

## Resumen

- Con el perfil de demanda de la UPME, el caso de 6 TS cuesta **lo mismo que el de 2 TS (−0,13 %)** y tarda **unas 10 veces más** en resolverse (~30–40 min frente a ~4 min).
- El costo casi no cambia, pero **sí cambian decisiones de planeación**:
  - menos electrificación del calor industrial (+1,4 % de GEI en 2055);
  - otro reparto entre eólica y solar;
  - la hidro de embalse llega a su tope en la tarde-noche.
- Pasar a 6 TS hizo **infactible** el modelo hasta que se ajustó la capacidad de las tecnologías de demanda a la punta (ver "Problemas encontrados").
- Al revisar las 76 gráficas de la app aparecieron **problemas del SAND que ya estaban en 2 TS**: capacidades gratis, carbón con margen cero y otros. Hay que reportarlos a la UPME.

## Archivos

Los SAND **no se versionan**. Viven en `tmp/sand/`, que está ignorado por git:

| Carpeta | Contenido |
|---|---|
| `tmp/sand/inputs/` | Entradas. Hay que copiarlas a mano: `PD_2TS_41D_2055_SAND_03Jun2026.xlsx` (SAND completo de 2 TS: `S101` día y `S102` noche, 12 h cada uno), `6TS_parameters_SAND.xlsx` (de la UPME: 608 filas con 6 parámetros, no un SAND completo; se usa solo como fuente de formas) y los exports de la BD `PD_scenario_168_…`, `PA_scenario_167_…` y `CN_scenario_166_Parameters_SAND.xlsx`. |
| `tmp/sand/outputs/` | SAND generados. **Entregables:** `PD/PA/CN_6TS_41D_2055_SAND_19Oct2026.xlsx`, con el mismo formato y los mismos nombres que el 2 TS. Las variantes quedan en `pd_6ts/`, `pa_6ts/` y `cn_6ts/`. |
| `tmp/sand/runs/` | Corridas de `run_osemosys_cli.py` (`<caso>/` y `<caso>.log`). |

Scripts en `backend/scripts/sand_6ts/`. Las rutas se definen en `common.py`.

| Script | Qué hace |
|---|---|
| `common.py` | Método común de 2 → 6 TS y CLI. |
| `build_pd_6ts.py`, `build_pa_6ts.py`, `build_cn_6ts.py` | Construyen y validan el SAND de 6 TS de cada escenario. |
| `compare_cases.py` | Compara corridas: costo, capacidad, generación por familia y por TS. |
| `ui_charts_from_runs.py` | Genera las 76 gráficas de la app a partir de corridas en modo Excel, con el motor de gráficas de la propia app. |
| `report_6ts_html.py` | Genera el reporte HTML comparativo de PD, PA y CN (plantilla `report_6ts_template.html`). |

## Estructura de los 6 TS

`YearSplit` viene del archivo de la UPME y es igual en todos los años:

| TS | Horas/año | Horas/día | Bloque |
|---|---|---|---|
| S101 / S201 | 1110 / 1080 | 6 | madrugada |
| S102 / S202 | 2035 / 1980 | 11 | día (con sol) |
| S103 / S203 | 1295 / 1260 | 7 | tarde-noche (punta) |

El semestre S1 tiene 185 días y el S2, 180. **Supuesto, pendiente de confirmar con la UPME:** madrugada 00–06 h, día 06–17 h y tarde-noche 17–24 h. Es consistente con las horas de cada bloque y con una solar ≈ 0 en la tarde-noche.

## Qué se tomó del archivo de 6 TS de la UPME

| Elemento | ¿Se usa? | Por qué |
|---|---|---|
| `YearSplit` | ✅ | Coherente y suma 1. |
| Forma del CF solar, eólico e hidro | ✅ Solo la forma | El nivel anual se calibra al del 2 TS. La forma aporta la estacionalidad hidro y el ciclo diario solar y eólico. |
| Perfil de demanda (punta ×1,077) | ⚠️ Punto de partida | Es un solo perfil para 5 fuels; se aplica a las 41 demandas de uso final con perfil (no todas eléctricas: incluye cocción, agua caliente y calor industrial con gas, GLP, carbón o biomasa). |
| AF de solar, eólica e hidro | ❌ | Junto con el CF produce una doble reducción (ver más abajo). |
| 36 demandas pasadas a `AccumulatedAnnualDemand` | ❌ | Pierden el perfil y desaparece la punta. |
| 2055 vacío, `PWRFOIL`, `GRDDSTELC`, CSP/BAT sin CF | ❌ | Errores de armado. |

## Cómo se construye el SAND de 6 TS

Se parte del 2 TS completo y solo cambian estos parámetros:

1. **`YearSplit`:** el de la UPME, sin `REGION`, igual que en el 2 TS.
2. **`SpecifiedDemandProfile`:** el perfil común de la UPME aplicado a los 41 fuels que ya tenían perfil. Con `--peak-ratio R`, la tarde-noche se fija en R veces el promedio, manteniendo la participación de cada semestre.
3. **`CapacityFactor`:** por tecnología y año, `L = Σ CF_2TS · YearSplit_2TS` es el nivel anual del 2 TS. Con eso:
   - Las tecnologías con forma en el archivo UPME (solar, eólica, hidro) quedan con `CF_ts = min(1, L · forma_ts / Σ forma·YearSplit)`.
   - CSP y SOLUGE_BAT, que tienen forma día/noche en el 2 TS, se mapean así: día → S102/S202; noche → madrugada y tarde-noche.
   - El resto repite su valor en los 6 TS.
   - Cada tecnología produce la **misma energía anual** que en el 2 TS; solo cambia en qué horas.
4. **Capacidad de las tecnologías que abastecen demandas con perfil:** `ResidualCapacity`, `TotalAnnualMaxCapacityInvestment`, `TotalAnnualMaxCapacity` y `TotalAnnualMinCapacity` se multiplican por el factor de punta `f = max_ts(SDP/YearSplit)` (1,0773 con el perfil UPME). `CapitalCost` y `FixedCost` se dividen por `f`. Es un cambio de unidad que no altera el costo por energía. `TotalAnnualMinCapacityInvestment` no se escala, para no forzar inversión adicional.

Los límites de actividad (energía anual), el AF y las demandas anuales no cambian.

**Validaciones del script:**
- `YearSplit` suma 1 y cada perfil de demanda suma 1;
- todos los CF están en [0, 1];
- la energía anual de cada tecnología es igual a la del 2 TS;
- **cada demanda con perfil puede cubrir su punta**: capacidad residual más la inversión permitida durante la vida útil, frente a la demanda del TS más alto.

**Formato:** el archivo de salida respeta el del 2 TS: hoja `Parameters`, encabezados de año como texto, valores decimales, `MODE_OF_OPERATION` como texto ("1") y los mismos nombres de parámetros, tecnologías, combustibles y emisiones.

## Problemas encontrados

### 1. El caso de 6 TS era infactible

En el SAND, las tecnologías de demanda tienen `ResidualCapacity` igual a la demanda anual, CF = 1 e inversión limitada: su capacidad alcanza justo para una carga plana. En 2 TS el perfil es 0,5/0,5, igual al `YearSplit`, y cuadra exacto. En 6 TS la tarde-noche pide ×1,077 y no alcanza:

- **2022–2024**, porque no se permite inversión y la capacidad residual no cubre la punta;
- **`TERCLIM_SPL` (aires split terciarios) en 2053–2055**, porque el tope de inversión acumulado durante la vida útil de 20 años da como máximo 4,57 y la punta necesita 4,77.

El IIS de HiGHS no terminó en tiempo razonable. La causa se aisló por bisección:
1. primero se separó la estructura de 6 TS, las formas de CF y el perfil de demanda;
2. luego se partieron las demandas por grupos (residencial, terciario, industrial, resto);
3. y por último, dentro del terciario.

Se corrigió con el punto 4 de la construcción y con el chequeo estático de punta.

### 2. Costo falso del ajuste de capacidad

Escalar la capacidad sin tocar el costo agregaba **+6 508** (+0,6 %) de costo fijo e inversión sin ningún cambio real. Se corrigió dividiendo `CapitalCost` y `FixedCost` por `f`.

### 3. Doble reducción AF × CF en el archivo de la UPME

La restricción anual del modelo (`PlannedMaintenance`) multiplica `AF × Σ(CF·YearSplit)`. El archivo de la UPME trae el promedio anual en el AF **y además** la forma en el CF. El factor efectivo queda en ≈ 0,06 para la solar y ≈ 0,15 para la eólica, y la hidro no alcanza su generación mínima histórica (en 2022 debe generar 202 PJ y solo puede 133). Por eso la variante "tal como la entregó la UPME" (`--variant upme`) es infactible.

## Resultados

Solver HiGHS, horizonte 2022–2055, costo total descontado:

| Caso | Punta tarde-noche | Costo | Δ vs 2 TS | Tiempo |
|---|---|---|---|---|
| 2 TS | — | 1 111 079 | — | 4 min |
| **6 TS perfil UPME (entregable)** | ×1,077 | **1 109 626** | **−0,13 %** | 29–40 min |
| 6 TS punta realista | ×1,15 | 1 110 137 | −0,08 % | 28 min |

- Ningún caso usa `BACKSTOP`.
- El archivo entregable se resolvió por separado y dio **exactamente** los mismos valores de producción y capacidad que el caso de trabajo.
- La punta ×1,15 es un supuesto: es el promedio de 7 h de una curva diaria típica, no un dato de la UPME. El pico horario real (×1,3–1,4) queda diluido en un bloque de 7 h; representarlo exigiría un bloque de punta más corto.

**Sector eléctrico**
- La punta de la tarde-noche se cubre con hidro de embalse. Con ×1,077 llega a 7,3–8,4 GW en S103/S203, que es su tope del bloque (CF 0,47 × 15,6 GW). Con ×1,15 la diferencia la ponen la eólica on-shore (+0,6 GW en 2030) y la térmica.
- La capacidad de hidro y gas no cambia entre casos. Lo que cambia es el reparto eólica–solar:

  | Capacidad 2055 (GW) | 2 TS | 6 TS UPME | 6 TS ×1,15 |
  |---|---|---|---|
  | Eólica | 19,8 | 16,4 | 17,8 |
  | Solar | 8,3 | 11,0 | 8,3 |

  El 2 TS sobrevalora la eólica porque le da el mismo CF de día y de noche.

**Demanda y emisiones**
- En 2055, los hornos eléctricos de alta temperatura en la industria caen de 19,4 a ~6,5 PJ y los hornos a carbón suben de 27,6 a 42–45 PJ.
- Resultado: +1,6–1,9 MtCO₂eq en la industria y **+1,4 % de GEI totales en 2055**.

**Desglose del costo (6 TS perfil UPME frente a 2 TS):** el sector eléctrico −98, las importaciones −829 y los equipos de uso final −504. Los intercambios de carbón y de carga se compensan entre sí (ver la sección siguiente).

## Problemas del SAND y de la app (independientes de los TS)

| Problema | Efecto | Origen |
|---|---|---|
| 58 tecnologías con capital y costo fijo en 0 e inversión máxima 99 999 | El modelo instala cualquier capacidad: barco diésel con 31 710 GW en 2 TS. Confirmado con una prueba: con un costo de 0,0001 baja a 33 PJ/año sin cambiar el costo ni la producción. | SAND |
| `DEMCOQDSL` (coquería) con `ResidualCapacity` = 99 999 | Capacidad irreal desde los datos | SAND |
| Carbón: exportación −2,57 y minería +2,57 por PJ (margen cero) | La minería y la exportación saltan hasta ±80 % entre corridas sin cambiar el costo | SAND |
| Carga liviana: gasolina e híbridos con el mismo costo | Se intercambian entre corridas y mueven hasta 10 % los contaminantes del transporte | SAND |
| AF × CF en el archivo de 6 TS de la UPME | Doble reducción e infactibilidad | Archivo UPME |
| "Emisiones - Total" y "Emisiones - Por Sector" sin filtro de tipo | Suman GEI (Mt) con contaminantes criterio (kt) | App (`configs_legacy.py`) |
| Otros Sectores, SAF y Crudo | Gráficas vacías: el SAND no tiene esas tecnologías | SAND |

## Cómo reproducir

Desde `backend/`:

```bash
# SAND de 6 TS (entregable) y variantes; por defecto escriben en tmp/sand/outputs/pd_6ts/
python scripts/sand_6ts/build_pd_6ts.py --out ../tmp/sand/outputs/PD_6TS_41D_2055_SAND_19Oct2026.xlsx
python scripts/sand_6ts/build_pd_6ts.py --peak-ratio 1.15      # punta realista
python scripts/sand_6ts/build_pd_6ts.py --variant upme         # tal como lo entregó la UPME (infactible)

# Resolver (una corrida a la vez). compare_cases.py lee el tiempo ("real") y
# report_6ts_html.py, la ruta del SAND, ambos desde el log.
/usr/bin/time -p python scripts/run_osemosys_cli.py excel ../tmp/sand/outputs/PD_6TS_41D_2055_SAND_19Oct2026.xlsx \
    --solver highs -o ../tmp/sand/runs/6TS_v19oct --overwrite > ../tmp/sand/runs/6TS_v19oct.log 2>&1

# Comparar y generar las gráficas de la app
python scripts/sand_6ts/compare_cases.py 2TS 6TS_v19oct
python scripts/sand_6ts/ui_charts_from_runs.py 2TS 6TS_v19oct
```

PA y CN se construyen igual, con `build_pa_6ts.py` y `build_cn_6ts.py`. Para el reporte HTML: `python scripts/sand_6ts/report_6ts_html.py`.

## Pendientes

1. **Para la UPME:**
   - qué meses son S1 y S2, y qué horas cubre cada bloque;
   - fuente de las formas de CF y del perfil de demanda;
   - perfiles de demanda por sector;
   - si fue deliberado pasar 36 demandas a `AccumulatedAnnualDemand`;
   - si fue deliberado poner la reducción en el AF;
   - corregir los problemas del SAND de la tabla anterior.
2. **Hidro de embalse:** con un CF fijo por bloque no puede concentrar agua en la punta. Evaluar modelarla con almacenamiento o con un CF más alto en punta, compensado en los otros bloques.
3. **App:** agregar el filtro de GEI a "Emisiones - Total" y "Emisiones - Por Sector".
4. **Ruta por la UI:** probar el archivo importándolo como escenario en la base de datos. Solo se probó la ruta de Excel SAND.
5. **Aislar el efecto de la punta:** comparar con una variante de formas de CF y demanda plana, guardando sus resultados.
