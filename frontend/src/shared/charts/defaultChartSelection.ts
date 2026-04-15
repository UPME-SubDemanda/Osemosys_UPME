import type { ChartSelection } from './ChartSelector';

/**
 * Debe coincidir con la primera entrada de `MENU` en ChartSelector (Sector Eléctrico → Producción).
 */
export function getDefaultChartSelection(): ChartSelection {
  return {
    tipo: 'elec_produccion',
    un: 'PJ',
    sub_filtro: '',
    loc: '',
    variable: '',
    viewMode: 'column',
    agrupar_por: 'TECNOLOGIA',
  };
}
