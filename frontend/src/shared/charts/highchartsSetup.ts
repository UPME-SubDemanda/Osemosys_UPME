/**
 * Shared Highcharts setup — initializes export modules exactly once.
 * All chart components should import Highcharts from this file.
 */
import Highcharts from 'highcharts';
import exporting from 'highcharts/modules/exporting';
import exportData from 'highcharts/modules/export-data';
import offlineExporting from 'highcharts/modules/offline-exporting';

if (typeof Highcharts === 'object') {
  exporting(Highcharts);
  exportData(Highcharts);
  offlineExporting(Highcharts);
}

export default Highcharts;
