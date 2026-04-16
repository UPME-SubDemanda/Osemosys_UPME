import { simulationApi } from '@/features/simulation/api/simulationApi';
import { downloadBlob } from '@/shared/utils/downloadBlob';
import type { ChartSelection } from './ChartSelector';

/**
 * Descarga PNG/SVG/CSV generados en el servidor (Matplotlib / CSV), sin offline-exporting.
 */
export async function downloadChartFromServer(
  jobId: number,
  selection: ChartSelection,
  fmt: 'png' | 'svg' | 'csv',
): Promise<void> {
  const { blob, filename } = await simulationApi.exportChart(jobId, selection, fmt);
  downloadBlob(blob, filename);
}
