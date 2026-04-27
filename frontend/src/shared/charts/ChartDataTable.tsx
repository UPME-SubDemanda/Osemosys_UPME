/**
 * ChartDataTable — renderiza un `ChartDataResponse` como tabla HTML.
 *
 * Es la "view_mode = table". Reusa el mismo dato que un chart de columnas
 * (`simulationApi.getChartData`) y aplica dos transformaciones opcionales en
 * cliente — paralelas a las del backend (`apply_period_years` y
 * `apply_cumulative_series` en `chart_service.py`):
 *   • `cumulative=true`  → cada serie muestra suma acumulada por categoría.
 *   • `periodYears=N`    → solo se muestran categorías cada N años.
 *
 * Las transformaciones en cliente garantizan que el render del visor sea
 * coherente con lo que se exporta vía `/export-chart` (ambos lados aplican
 * la misma lógica). Para PNG/SVG/CSV/XLSX descarga al backend con los mismos
 * parámetros vía `serverChartExport`.
 */
import React, { useMemo, useState } from 'react';
import type { ChartDataResponse } from '../../types/domain';
import type { ChartSelection } from './ChartSelector';
import { formatAxis3Sig } from './numberFormat';
import { downloadChartFromServer } from './serverChartExport';

interface Props {
  data: ChartDataResponse;
  /** Filtra categorías-año cada N. `null`/undefined = todos. */
  periodYears?: number | null;
  /** Si true, los valores se muestran como suma acumulada por serie. */
  cumulative?: boolean;
  /** Para descargar PNG/SVG/CSV/XLSX desde el backend. */
  serverExport?: { jobId: number; selection: ChartSelection };
}

/** Espejo de `_year_keep_indices` en backend. Categorías no-año se preservan. */
function yearKeepIndices(
  categories: ReadonlyArray<string | number>,
  period: number | null | undefined,
): number[] {
  if (!period || period < 2) return categories.map((_, i) => i);
  // Buscar índices que sean años parseables y aplicar el paso.
  const yearIdx: number[] = [];
  const yearVal: number[] = [];
  for (let i = 0; i < categories.length; i += 1) {
    const raw = categories[i];
    const y = typeof raw === 'number' ? raw : parseInt(String(raw), 10);
    if (!Number.isNaN(y)) {
      yearIdx.push(i);
      yearVal.push(y);
    }
  }
  if (yearIdx.length === 0) return categories.map((_, i) => i);
  const base = yearVal[0]!;
  const keep = new Set<number>();
  // Categorías no-año siempre se preservan.
  for (let i = 0; i < categories.length; i += 1) {
    if (!yearIdx.includes(i)) keep.add(i);
  }
  for (let k = 0; k < yearIdx.length; k += 1) {
    if ((yearVal[k]! - base) % period === 0) keep.add(yearIdx[k]!);
  }
  // Garantizar el último año.
  keep.add(yearIdx[yearIdx.length - 1]!);
  return Array.from(keep).sort((a, b) => a - b);
}

/** Espejo de `apply_cumulative_series` en backend (no muta la entrada). */
function applyCumulative(data: (number | null)[]): number[] {
  let running = 0;
  return data.map((v) => {
    const f = typeof v === 'number' && Number.isFinite(v) ? v : 0;
    running += f;
    return running;
  });
}

export const ChartDataTable: React.FC<Props> = ({
  data,
  periodYears,
  cumulative,
  serverExport,
}) => {
  const [downloading, setDownloading] = useState<null | 'png' | 'svg' | 'csv' | 'xlsx'>(
    null,
  );
  const [menuOpen, setMenuOpen] = useState(false);

  const view = useMemo(() => {
    // 1) Acumular (si aplica) sobre TODAS las categorías originales.
    const seriesCum = data.series.map((s) => ({
      ...s,
      data: cumulative ? applyCumulative(s.data) : s.data.slice(),
    }));
    // 2) Filtrar columnas por período.
    const keep = yearKeepIndices(data.categories, periodYears ?? null);
    const cats = keep.map((i) => data.categories[i]!);
    const series = seriesCum.map((s) => ({
      ...s,
      data: keep.map((i) => (i < s.data.length ? s.data[i]! : 0)),
    }));
    // 3) Totales por columna.
    const totals = cats.map((_, colIdx) =>
      series.reduce((acc, s) => acc + (Number.isFinite(s.data[colIdx]) ? s.data[colIdx]! : 0), 0),
    );
    return { cats, series, totals };
  }, [data, cumulative, periodYears]);

  const handleDownload = async (fmt: 'png' | 'svg' | 'csv' | 'xlsx') => {
    if (!serverExport) return;
    setDownloading(fmt);
    setMenuOpen(false);
    try {
      await downloadChartFromServer(
        serverExport.jobId,
        serverExport.selection,
        fmt,
      );
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('[ChartDataTable] download error', err);
      alert('No se pudo descargar la tabla.');
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="w-full">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="min-w-0">
          <h3 className="m-0 text-sm font-semibold text-slate-100 break-words">
            {data.title}
          </h3>
          <p className="m-0 text-[11px] text-slate-500">
            {data.yAxisLabel}
            {periodYears && periodYears >= 2 ? ` · cada ${periodYears} años` : ''}
            {cumulative ? ' · acumulado' : ''}
          </p>
        </div>
        {serverExport ? (
          <div className="relative">
            <button
              type="button"
              onClick={() => setMenuOpen((v) => !v)}
              className="rounded border border-slate-700 bg-slate-800 px-2 py-1 text-xs text-slate-200 hover:bg-slate-700"
              disabled={downloading != null}
            >
              {downloading ? 'Descargando…' : 'Descargar ▾'}
            </button>
            {menuOpen ? (
              <div className="absolute right-0 top-full z-30 mt-1 w-40 rounded-lg border border-slate-700 bg-slate-900 shadow-2xl">
                {(['png', 'svg', 'csv', 'xlsx'] as const).map((f) => (
                  <button
                    key={f}
                    type="button"
                    onClick={() => void handleDownload(f)}
                    className="block w-full px-3 py-2 text-left text-xs text-slate-200 hover:bg-slate-800"
                  >
                    Descargar {f.toUpperCase()}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="overflow-auto rounded-lg border border-slate-800 max-h-[60vh]">
        <table className="min-w-full border-collapse text-xs text-slate-200">
          <thead className="bg-slate-800 sticky top-0 z-10">
            <tr>
              <th className="px-3 py-2 text-left font-semibold uppercase tracking-wider text-[10px] text-slate-300 border-r border-slate-700">
                Tecnología
              </th>
              {view.cats.map((c, i) => (
                <th
                  key={`h-${i}`}
                  className="px-3 py-2 text-right font-semibold uppercase tracking-wider text-[10px] text-slate-300"
                >
                  {String(c)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {view.series.map((s, rIdx) => (
              <tr
                key={`r-${rIdx}-${s.name}`}
                className={rIdx % 2 === 0 ? 'bg-slate-900/40' : 'bg-slate-900/20'}
              >
                <td
                  className="px-3 py-1.5 font-semibold text-white border-r border-slate-700/60"
                  style={{ background: s.color, minWidth: 180 }}
                  title={s.name}
                >
                  {s.name}
                </td>
                {view.cats.map((_c, cIdx) => (
                  <td
                    key={`c-${rIdx}-${cIdx}`}
                    className="px-3 py-1.5 text-right tabular-nums text-slate-100 whitespace-nowrap"
                  >
                    {formatAxis3Sig(s.data[cIdx])}
                  </td>
                ))}
              </tr>
            ))}
            {view.series.length > 0 ? (
              <tr className="bg-slate-700/60 font-semibold">
                <td className="px-3 py-1.5 text-white border-r border-slate-700/60">
                  Total
                </td>
                {view.totals.map((t, cIdx) => (
                  <td
                    key={`t-${cIdx}`}
                    className="px-3 py-1.5 text-right tabular-nums text-white whitespace-nowrap"
                  >
                    {formatAxis3Sig(t)}
                  </td>
                ))}
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
};
