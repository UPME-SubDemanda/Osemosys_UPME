# SAND PD de 8 TS: bloque de punta corto

**Estado (20-oct-2026):** caso construido, resuelto (óptimo) y verificado. Archivo entregable: `tmp/sand/outputs/PD_8TS_41D_2055_SAND_20Oct2026.xlsx`. Parte del 6 TS de `docs/sand-6ts-migracion.md`.

## Por qué

En el 6 TS de la UPME, la tarde-noche es un bloque de 7 h (17–24 h) con demanda ×1,077 del promedio. El pico horario real (×1,3–1,4) queda diluido en ese bloque, y el modelo casi no ve la punta.

Hay dos formas de hacerla visible, y ninguna convence:
- **Subir todo el bloque de 7 h:** exagera la energía de la tarde-noche.
- **Darle a la hidro de embalse un CF más alto en la punta:** esconde justo lo que se quiere ver, que la hidro, con un CF fijo por bloque, no puede seguir la punta.

Por eso aquí se agrega un bloque de punta corto y se conserva la energía del bloque de la UPME.

## Estructura

Cada tarde-noche del 6 TS se parte en dos bloques. El resto de la estructura no cambia.

| TS | Bloque | h/día | Horas/año | Demanda / promedio |
|---|---|---|---|---|
| S101 / S201 | madrugada | 6 | 1110 / 1080 | 0,83 / 0,84 |
| S102 / S202 | día | 11 | 2035 / 1980 | 1,04 / 1,05 |
| **S103 / S203** | **punta 18–21 h** | 3 | 555 / 540 | **1,30** |
| S104 / S204 | resto (17–18 h y 21–24 h) | 4 | 740 / 720 | 0,90 / 0,91 |

- **Demanda:** punta = 1,30 × YearSplit; resto = SDP de la tarde-noche del 6 TS − punta. Cada perfil sigue sumando 1 y la tarde-noche conserva su energía.
- **CF:** la punta y el resto repiten el CF de la tarde-noche del 6 TS para todas las tecnologías, también la hidro. La energía anual de cada tecnología es igual a la del 2 TS.
- **Capacidad de las tecnologías de demanda:** el factor de punta sube a 1,30. Se escalan ResidualCapacity y los topes de 146 tecnologías, y su CapitalCost y FixedCost se dividen por el mismo factor (costo neutro), igual que en el 6 TS.
- **Supuestos para confirmar con la UPME:** punta de 18 a 21 h y ratio ×1,30, que es el promedio de 3 h de una curva con pico horario ×1,3–1,4.

## Resultados (PD, HiGHS, 2022–2055)

| Caso | Costo total | Δ vs 2 TS | Costo sector eléctrico (PWR) | Tiempo |
|---|---|---|---|---|
| 2 TS | 1 111 079 | — | 29 168 | 4 min |
| 6 TS | 1 109 626 | −0,13 % | 29 071 | 29 min |
| **8 TS** | **1 111 192** | **+0,01 %** | **32 056 (+10,3 % vs 6 TS)** | **61 min** |

El costo total casi no se mueve porque la generación eléctrica es ~3 % del costo del sistema: los equipos de uso final pesan 81 %. Por eso el indicador útil es el costo del sector eléctrico, que **sube 10 %** con la punta.

### Quién cubre la punta

| GW medios en la punta | 2030 6 TS → 8 TS | 2040 6 TS → 8 TS | 2055 6 TS → 8 TS |
|---|---|---|---|
| Punta del sistema | 10,2 (día) → **10,6 (S103)** | 13,7 → 14,3 (día) | 19,5 (día) → **19,5 (S103)** |
| Gas en S103 | 0,22 → **0,69** | 0 → **1,12** | 0 → **0,79** (S203: 1,12) |
| Hidro embalse en S103/S203 | en su tope | en su tope | en su tope |

- **Hidro:** el embalse queda en su tope en la punta todos los años, como se esperaba. En 2030 no llena el resto de la tarde-noche (91–95 %), y esa agua no puede pasarse a la punta: la hidro anual baja de 189,0 a 186,7 PJ.
- **Gas:** la punta adicional la cubre la **capacidad de gas existente** (2,95 GW), sin inversión nueva. El gas pasa de casi cero a 0,7–1,1 GW en el bloque de punta.

### Cambios de planeación (capacidad, GW)

| | 2030 6 TS → 8 TS | 2040 | 2055 |
|---|---|---|---|
| Eólica | 1,20 → **3,68** | 4,97 → 5,33 | 16,42 → **17,85** |
| Solar | 9,73 → 9,73 | 11,41 → 11,41 | 11,02 → **9,18** |
| Gas, hidro, carbón | sin cambio | sin cambio | sin cambio |

- **Eólica:** se adelanta (+2,5 GW en 2030) porque tiene CF en la tarde-noche y ayuda en la punta. En 2055 queda entre el 6 TS y el 2 TS.
- **Solar:** no aporta en la punta (CF ≈ 0). En 2030 se vierte parte: con la misma capacidad genera 62,0 PJ en vez de 69,7. En 2055 se instalan 1,8 GW menos.

### Demanda y emisiones

| GEI (CO₂ + CH₄ + N₂O, Mt) | 2 TS | 6 TS | 8 TS |
|---|---|---|---|
| 2030 | 78,3 | 77,9 | **76,1** |
| 2040 | 85,5 | 85,5 | 84,1 |
| 2055 | 102,7 | 104,1 | 103,9 |

- **GEI:** bajan en 2030 y 2040, por más eólica y menos carbón en la generación. En 2055 son iguales a los del 6 TS.
- **Calor industrial en 2055:** se reacomoda. Las calderas de gas MID caen de 23,9 a 4,4 PJ, y suben el carbón (hornos y calderas, +15 PJ) y el bagazo. Por eso el SOx de 2055 sube +16 % (144 → 166 kt). Una parte de este cambio puede ser ruido: el carbón tiene margen cero en el SAND (ver el doc de 6 TS).

## Conclusión

El 8 TS **sí cambia decisiones** que el 6 TS no ve:
- adelanta la eólica 2,5 GW en 2030;
- reduce la solar 1,8 GW en 2055;
- obliga a usar el gas existente en la punta.

También hace explícita la limitación de la hidro. **Se recomienda adoptar el 8 TS** como entregable del PD, con dos salvedades:
1. **Tiempo:** tarda el doble que el 6 TS en resolverse (61 min frente a 29).
2. **Hidro pesimista:** sin almacenamiento, el modelo no deja al embalse mover agua del resto a la punta. El 8 TS es una cota pesimista para la hidro en punta.

La punta no exigió capacidad firme nueva en ningún año: alcanza la térmica existente. Eso se debe en parte a que el margen de reserva del SAND está inactivo, porque ningún fuel tiene `ReserveMarginTagFuel`.

## Cómo reproducir

Desde `backend/` (las entradas en `tmp/sand/inputs/`, ver el doc de 6 TS):

```bash
python scripts/sand_8ts/build_pd_8ts.py --out ../tmp/sand/outputs/PD_8TS_41D_2055_SAND_20Oct2026.xlsx
python scripts/sand_8ts/build_pd_8ts.py --peak-hours 2 --peak-ratio 1.35   # sensibilidad

/usr/bin/time -p python scripts/run_osemosys_cli.py excel ../tmp/sand/outputs/PD_8TS_41D_2055_SAND_20Oct2026.xlsx \
    --solver highs -o ../tmp/sand/runs/8TS_PB3H130 --overwrite > ../tmp/sand/runs/8TS_PB3H130.log 2>&1

python scripts/sand_6ts/compare_cases.py 2TS 6TS_v19oct 8TS_PB3H130
python scripts/sand_8ts/peak_analysis.py 6TS_v19oct 8TS_PB3H130 --years 2030 2040 2055
```

El entregable es idéntico, en contenido, al archivo del caso resuelto (`pd_8ts/PD_8TS_41D_2055_SAND_CAL_PB3H130.xlsx`).

## Pendientes

1. **Para la UPME:** confirmar la hora y el ratio de la punta. Si hay curva horaria, el ratio debe ser el promedio de las 3 h de mayor demanda.
2. **Sensibilidad:** probar una punta de 2 h × 1,35 y activar el margen de reserva para ELC.
3. **PA y CN en 8 TS**, con scripts propios en `scripts/sand_8ts/`.
4. **Hidro de embalse con almacenamiento**, para no subestimar su aporte en la punta.
