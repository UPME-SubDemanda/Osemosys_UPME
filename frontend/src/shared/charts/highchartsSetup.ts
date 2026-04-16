/**
 * Shared Highcharts setup — initializes export modules exactly once.
 * All chart components should import Highcharts from this file.
 *
 * PNG local: offline-exporting intenta cargar `canvg.js` desde `code.highcharts.com`;
 * en muchas redes eso falla (403, firewall, CSP). Precargamos `canvg` v3 desde npm
 * (`Canvg.fromString`, API que espera Highcharts) en `window.canvg` para no usar el CDN.
 */
import Highcharts from 'highcharts';
import Canvg from 'canvg';
import exporting from 'highcharts/modules/exporting';
import exportData from 'highcharts/modules/export-data';
import offlineExporting from 'highcharts/modules/offline-exporting';

if (typeof Highcharts === 'object') {
  exporting(Highcharts);
  exportData(Highcharts);
  offlineExporting(Highcharts);

  if (typeof window !== 'undefined') {
    const w = window as Window & { canvg?: { Canvg: typeof Canvg } };
    w.canvg = { Canvg };
  }

  Highcharts.setOptions({
    lang: {
      downloadPNG: 'Descargar PNG',
      downloadJPEG: 'Descargar JPEG',
      downloadPDF: 'Descargar PDF',
      downloadSVG: 'Descargar SVG',
      downloadCSV: 'Descargar CSV',
      downloadXLS: 'Descargar XLS',
    },
  });
}

export default Highcharts;
