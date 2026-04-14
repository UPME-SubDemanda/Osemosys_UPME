/**
 * Botón de menú de exportación con fondo oscuro (el predeterminado es blanco y destaca en capturas PNG).
 */
export const EXPORTING_CONTEXT_BUTTON_DARK = {
  theme: {
    fill: "#0f172a",
    stroke: "#334155",
    states: {
      hover: { fill: "#1e293b", stroke: "#475569" },
      select: { fill: "#1e293b", stroke: "#475569" },
    },
  },
  symbolStroke: "#94a3b8",
} as const;

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
