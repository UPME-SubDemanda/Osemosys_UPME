/** Orientación de barras en gráficos de columnas apiladas. */
export type ChartBarOrientation = 'vertical' | 'horizontal';

/** Cómo se colocan varias gráficas en modo comparación por escenario (facetas). */
export type ChartFacetPlacement = 'inline' | 'stacked';

/**
 * Leyenda en comparación por escenarios (facetas):
 * - shared: panel único encima de todas las gráficas (recomendado).
 * - perFacet: leyenda nativa de Highcharts solo en la primera faceta.
 */
export type ChartFacetLegendMode = 'shared' | 'perFacet';

const BAR_KEY = 'osemosys-chart-bar-orientation';
const FACET_KEY = 'osemosys-chart-facet-placement';
const LEGEND_KEY = 'osemosys-chart-facet-legend-mode';

export function loadChartBarOrientation(): ChartBarOrientation {
  try {
    const v = localStorage.getItem(BAR_KEY);
    if (v === 'horizontal') return 'horizontal';
  } catch {
    /* ignore */
  }
  return 'vertical';
}

export function saveChartBarOrientation(value: ChartBarOrientation): void {
  try {
    localStorage.setItem(BAR_KEY, value);
  } catch {
    /* ignore */
  }
}

export function loadChartFacetPlacement(): ChartFacetPlacement {
  try {
    const v = localStorage.getItem(FACET_KEY);
    if (v === 'stacked') return 'stacked';
  } catch {
    /* ignore */
  }
  return 'inline';
}

export function saveChartFacetPlacement(value: ChartFacetPlacement): void {
  try {
    localStorage.setItem(FACET_KEY, value);
  } catch {
    /* ignore */
  }
}

export function loadChartFacetLegendMode(): ChartFacetLegendMode {
  try {
    const v = localStorage.getItem(LEGEND_KEY);
    if (v === 'perFacet') return 'perFacet';
  } catch {
    /* ignore */
  }
  return 'shared';
}

export function saveChartFacetLegendMode(value: ChartFacetLegendMode): void {
  try {
    localStorage.setItem(LEGEND_KEY, value);
  } catch {
    /* ignore */
  }
}
