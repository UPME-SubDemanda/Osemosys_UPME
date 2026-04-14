/**
 * Callback de Highcharts cuando falla la exportación local (offline-exporting).
 * API: exporting.error(exportingOptions, err) — ver módulo offline-exporting.
 * Sin esto el fallo puede ser silencioso si fallbackToExportServer es false.
 */
export function onHighchartsExportError(
  _exportingOptions: unknown,
  err: unknown,
): void {
  console.error('Highcharts export', err);
  window.alert(
    'No se pudo exportar el SVG desde el navegador. Usa el menú Exportar para descargar un ZIP con todas las gráficas.',
  );
}
