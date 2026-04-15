import type Highcharts from "highcharts";

/**
 * Apariencia al exportar SVG (misma base que `exporting.chartOptions` en las gráficas de barras).
 * Se reutiliza en Chart#getSVG para la descarga combinada de facetas.
 */
export const HIGHCHARTS_GETSVG_MERGE_OPTIONS: Partial<Highcharts.Options> = {
  chart: {
    backgroundColor: "#FFFFFF",
    plotBorderWidth: 1,
    plotBorderColor: "#94a3b8",
  },
  title: { style: { color: "#1e293b", fontSize: "28px" } },
  xAxis: {
    labels: {
      style: { color: "#334155", fontSize: "24px" },
      rotation: -90,
      align: "right",
      /** Sin esto Highcharts fuerza -45° al exportar. `false` es válido en runtime (tipos incompletos). */
      autoRotation: false,
    } as unknown as Highcharts.XAxisLabelsOptions,
    lineColor: "#334155",
    lineWidth: 1,
    tickColor: "#334155",
    tickWidth: 1,
  },
  yAxis: {
    labels: { style: { color: "#334155", fontSize: "22px" } },
    title: { style: { color: "#334155", fontSize: "24px" } },
    lineColor: "#334155",
    lineWidth: 1,
    gridLineColor: "#e2e8f0",
    stackLabels: { style: { color: "#1e293b", fontSize: "18px" } },
  },
  legend: { itemStyle: { color: "#334155", fontSize: "20px" } },
};

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
