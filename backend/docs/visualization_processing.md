# Procesamiento de Resultados y Visualización en OSeMOSYS

## Flujo de Trabajo

El procesamiento de resultados en esta arquitectura de OSeMOSYS se centra en la eficiencia, moviendo el peso computacional del cliente (navegador) al servidor (backend Python).

1. **Simulación:** Tras la resolución del modelo por el *solver* (HiGHS o GLPK), el sistema guarda los datos crudos en la base de datos (PostgreSQL), incluyendo varibles intermedias calculadas y resultados paramétricos en la tabla `osemosys_output_param_value`.
2. **Petición del Cliente:** El frontend en React interactúa mediante `simulationApi` para solicitar datos en endpoints específicos (ej. `/visualizations/{job_id}/chart-data` o `/visualizations/chart-data/compare`).
3. **Procesamiento Backend:** El archivo `app/visualization/chart_service.py` lee las configuraciones desde `configs.py`. Mediante Pandas, realiza funciones de:
    - Agrupación por tecnologías, combustibles o años (`groupby`).
    - Filtros por "Pico", "Valle" o "Acumulado" mediante el sub-filtro correspondiente.
    - Conversión de unidades dinámicas (ej. de PJ a diferentes magnitudes).
    - Asignación de una paleta de colores oficial dictada por `colors.py` para asegurar consistencia regional y tecnológica.
4. **Cache:** El resultado del DataFrame empaquetado como objeto Pydantic (`ChartDataResponse`) es cacheado en **Redis** para responder instantáneamente ante peticiones con los mismos parámetros.
5. **Renderizado Frontend:** El Frontend (React) toma la estructura limpia enviada y la traduce en componentes interactivos de `Highcharts`. Así, componentes como `HighchartsChart.tsx` o `CompareChart.tsx` están puramente enfocados a la capa visual sin involucrar operaciones intensivas en el DOM.

## Comparación de Escenarios
Cuando se habilita la comparación (`CompareChart.tsx`), el backend extrae en paralelo los escenarios solicitados, concatena y alinea los sub-DataFrames, y entrega una estructura `CompareChartResponse` conteniendo múltiples *subplots* que Highcharts dibuja como gráficas de columnas sincronizadas.

## Herramientas de Exportación
El dashboard incluye una vía de rescate que comprime toda la selección de gráficas SVG de un escenario a una alta calidad vía la librería *Matplotlib* generada del lado del servidor. El usuario puede entonces descargarlas empaquetadas en un único `.zip`.
