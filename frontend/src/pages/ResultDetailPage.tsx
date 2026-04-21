import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import type { LucideIcon } from 'lucide-react';
import {
  AlignLeft,
  BarChart3,
  DollarSign,
  GalleryHorizontal,
  GalleryVertical,
  LayoutGrid,
  Layers,
  Leaf,
  List,
  PanelBottom,
  Zap,
} from 'lucide-react';
import { simulationApi } from '../features/simulation/api/simulationApi';
import type {
  ResultSummaryResponse,
  ChartDataResponse,
  CompareChartResponse,
  CompareChartFacetResponse,
  CompareMode,
  RunResult,
  SimulationRun,
} from '../types/domain';
import { paths } from '../routes/paths';
import { ChartSelector, type ChartSelection } from '../shared/charts/ChartSelector';
import { getDefaultChartSelection } from '../shared/charts/defaultChartSelection';
import { ScenarioComparer, type CompareViewMode } from '../shared/charts/ScenarioComparer';
import { HighchartsChart } from '../shared/charts/HighchartsChart';
import { LineChart } from '../shared/charts/LineChart';
import { CompareChart } from '../shared/charts/CompareChart';
import { CompareChartFacet } from '../shared/charts/CompareChartFacet';
import type {
  ChartBarOrientation,
  ChartFacetLegendMode,
  ChartFacetPlacement,
} from '../shared/charts/chartLayoutPreferences';
import {
  loadChartBarOrientation,
  loadChartFacetLegendMode,
  loadChartFacetPlacement,
  saveChartBarOrientation,
  saveChartFacetLegendMode,
  saveChartFacetPlacement,
} from '../shared/charts/chartLayoutPreferences';
import { Button } from '../shared/components/Button';
import { downloadBlob } from '../shared/utils/downloadBlob';
import { formatCompactNumber, formatPercent } from '../shared/utils/numberFormat';

const MAX_COMPARE_COLUMNS = 4;
const EXECUTIONS_TABLE_PAGE_SIZE = 10;

const BADGE_OPTIMAL =
  'inline-flex shrink-0 items-center px-2 py-1 rounded-full bg-green-500/10 text-green-400 text-xs font-bold border border-green-500/20';

function getSolverStatusPresentation(statusRaw: string): { label: string; badgeClass: string } {
  const trimmed = statusRaw.trim();
  const label = (trimmed || 'UNKNOWN').toUpperCase();
  const s = trimmed.toLowerCase();

  const pill =
    'inline-flex shrink-0 items-center px-2 py-1 rounded-full text-xs font-bold border';

  if (s.includes('optimal')) {
    return { label, badgeClass: BADGE_OPTIMAL };
  }
  if (s.includes('infeasible')) {
    return {
      label,
      badgeClass: `${pill} bg-rose-500/10 text-rose-400 border-rose-500/20`,
    };
  }
  if (s.includes('unbounded')) {
    return {
      label,
      badgeClass: `${pill} bg-violet-500/10 text-violet-400 border-violet-500/20`,
    };
  }
  if (s.includes('limit') || s.includes('interrupt') || s.includes('stopped')) {
    return {
      label,
      badgeClass: `${pill} bg-amber-500/10 text-amber-400 border-amber-500/20`,
    };
  }
  if (s.includes('fail') || s.includes('error')) {
    return {
      label,
      badgeClass: `${pill} bg-red-500/10 text-red-400 border-red-500/20`,
    };
  }
  return {
    label,
    badgeClass: `${pill} bg-slate-500/10 text-slate-400 border-slate-500/20`,
  };
}

type ScenarioCardProps = {
  summary: ResultSummaryResponse;
  isCurrent?: boolean;
};

function ScenarioCard({ summary, isCurrent = false }: ScenarioCardProps) {
  const status = getSolverStatusPresentation(summary.solver_status);
  const title = summary.scenario_name?.trim() || `Job #${summary.job_id}`;

  return (
    <div
      className={[
        'bg-[#0f172a] border border-slate-800 rounded-xl p-5 shadow-2xl',
        isCurrent ? 'ring-2 ring-cyan-500/35' : '',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <header className="flex flex-col gap-3 pb-4 border-b border-slate-800/60 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
        <div className="min-w-0 flex-1 space-y-1.5">
          <p className="m-0 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">
            Escenario
          </p>
          <div className="flex flex-wrap items-center gap-2.5">
            <Link
              to={`/app/results/${summary.job_id}`}
              className="text-lg font-bold text-white hover:text-cyan-400 hover:underline break-words"
            >
              {title}
            </Link>
            {isCurrent ? (
              <span className="inline-flex shrink-0 items-center rounded-full border border-cyan-500/25 bg-cyan-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-cyan-400">
                Actual
              </span>
            ) : null}
          </div>
          <p className="m-0 text-xs text-slate-500 font-mono">Job #{summary.job_id}</p>
        </div>
        <span className={`${status.badgeClass} self-start sm:mt-0.5`}>{status.label}</span>
      </header>

      <div className="pt-3 flex flex-col gap-1">
        <ScenarioMetricRow
          icon={DollarSign}
          label="Objective Value (USD)"
          value={formatCompactNumber(summary.objective_value, 2)}
          highlight
        />
        <ScenarioMetricRow
          icon={Zap}
          label="Demand Coverage"
          value={formatPercent(summary.coverage_ratio, 2)}
        />
        <ScenarioMetricRow
          icon={Leaf}
          label="CO₂ Emissions (MtCO₂eq)"
          value={formatCompactNumber(summary.total_co2, 2)}
        />
      </div>
    </div>
  );
}

function ScenarioMetricRow({
  icon: Icon,
  label,
  value,
  highlight = false,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className="flex justify-between items-center gap-4 py-2 border-b border-slate-800/50 last:border-0">
      <span className="text-slate-400 text-sm flex items-center gap-2 min-w-0">
        <Icon className="w-4 h-4 shrink-0 text-slate-500" aria-hidden />
        {label}
      </span>
      <span
        className={[
          'font-mono font-bold tabular-nums text-right shrink-0',
          highlight ? 'text-cyan-300 text-[15px]' : 'text-white',
        ].join(' ')}
      >
        {value}
      </span>
    </div>
  );
}

export function ResultDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const currentRunId = Number(runId);

  // Summary & error
  const [summary, setSummary] = useState<ResultSummaryResponse | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runResult, setRunResult] = useState<RunResult | null>(null);
  const [runMeta, setRunMeta] = useState<SimulationRun | null>(null);

  // All summaries for comparison table
  const [allSummaries, setAllSummaries] = useState<ResultSummaryResponse[]>([]);
  const [loadingSummaries, setLoadingSummaries] = useState(true);
  /** Hasta 4 jobs para la vista en columnas (independiente de la comparación de gráficos). */
  const [selectedCompareColumnJobIds, setSelectedCompareColumnJobIds] = useState<number[]>([]);
  /** Disposición de las tarjetas KPI: cuadrícula o lista compacta. */
  const [scenarioCardsViewMode, setScenarioCardsViewMode] = useState<'grid' | 'list'>('grid');
  /** Paginación de la tabla de ejecuciones (comparativa). */
  const [executionsTablePage, setExecutionsTablePage] = useState(1);
  /** Solo reinicia la selección por defecto al cambiar de run; no en cada nuevo array `allSummaries`. */
  const compareColumnInitKeyRef = useRef<number | null>(null);
  const selectedCompareColumnJobIdsRef = useRef(selectedCompareColumnJobIds);
  selectedCompareColumnJobIdsRef.current = selectedCompareColumnJobIds;

  // Chart selector (tipo por defecto = primera gráfica del catálogo)
  const [chartSelection, setChartSelection] = useState<ChartSelection>(() => getDefaultChartSelection());

  // Comparison state unificado (CompareMode enum)
  const [compareState, setCompareState] = useState<{
    mode: CompareMode;
    jobIds: number[];
    yearsToPlot: number[];
  }>({
    mode: 'off',
    jobIds: [currentRunId],
    yearsToPlot: [2024, 2030, 2040, 2050],
  });

  // Chart data
  const [singleChartData, setSingleChartData] = useState<ChartDataResponse | null>(null);
  const [compareChartData, setCompareChartData] = useState<CompareChartResponse | null>(null);
  const [compareFacetData, setCompareFacetData] = useState<CompareChartFacetResponse | null>(null);
  const [loadingChart, setLoadingChart] = useState(false);

  const [chartBarOrientation, setChartBarOrientation] = useState<ChartBarOrientation>(() =>
    loadChartBarOrientation(),
  );
  const [chartFacetPlacement, setChartFacetPlacement] = useState<ChartFacetPlacement>(() =>
    loadChartFacetPlacement(),
  );
  const [chartFacetLegendMode, setChartFacetLegendMode] = useState<ChartFacetLegendMode>(() =>
    loadChartFacetLegendMode(),
  );

  useEffect(() => {
    saveChartBarOrientation(chartBarOrientation);
  }, [chartBarOrientation]);

  useEffect(() => {
    saveChartFacetPlacement(chartFacetPlacement);
  }, [chartFacetPlacement]);

  useEffect(() => {
    saveChartFacetLegendMode(chartFacetLegendMode);
  }, [chartFacetLegendMode]);

  // Export state: 'svg' | 'excel' mientras se descarga, null si no
  const [exportingType, setExportingType] = useState<'svg' | 'excel' | null>(null);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement>(null);
  const hasInfeasibilityDetails = Boolean(runResult?.infeasibility_diagnostics);
  const normalizedSolverStatus = (
    summary?.solver_status ?? runResult?.solver_status ?? ''
  ).toLowerCase();
  const isOptimal = normalizedSolverStatus.includes('optimal');
  const isNonOptimal = Boolean(summary || runResult) && !isOptimal;
  const failureMessage = runMeta?.error_message?.trim() || null;

  // 1. Fetch current run summary
  useEffect(() => {
    if (!currentRunId) return;
    setLoadingSummary(true);
    simulationApi
      .getResultSummary(currentRunId)
      .then(setSummary)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : 'Error loading summary'),
      )
      .finally(() => setLoadingSummary(false));
  }, [currentRunId]);

  useEffect(() => {
    if (!currentRunId) return;
    simulationApi
      .getResult(currentRunId)
      .then(setRunResult)
      .catch((err: unknown) => {
        console.error('Error loading full result', err);
        setRunResult(null);
      });
  }, [currentRunId]);

  useEffect(() => {
    if (!currentRunId) return;
    simulationApi
      .getRun(currentRunId)
      .then(setRunMeta)
      .catch((err: unknown) => {
        console.error('Error loading run metadata', err);
        setRunMeta(null);
      });
  }, [currentRunId]);

  // 2. Fetch all summaries for comparison table
  useEffect(() => {
    setLoadingSummaries(true);
    simulationApi
      .listRuns({ scope: 'global', status_filter: 'SUCCEEDED', cantidad: 50 })
      .then(async (res) => {
        const runs = res.data || [];
        const summaries = await Promise.all(
          runs.map((run) => simulationApi.getResultSummary(run.id).catch(() => null)),
        );
        setAllSummaries(summaries.filter(Boolean) as ResultSummaryResponse[]);
      })
      .catch(console.error)
      .finally(() => setLoadingSummaries(false));
  }, []);

  useEffect(() => {
    if (loadingSummaries || allSummaries.length === 0) return;
    if (!currentRunId || Number.isNaN(currentRunId)) {
      setSelectedCompareColumnJobIds([]);
      compareColumnInitKeyRef.current = null;
      return;
    }
    if (compareColumnInitKeyRef.current === currentRunId) return;

    const head = allSummaries[0];
    if (!head) return;

    const hasCurrent = allSummaries.some((s) => Number(s.job_id) === Number(currentRunId));
    const firstId = Number(head.job_id);
    const defaultIds = hasCurrent ? [currentRunId] : [firstId];
    setSelectedCompareColumnJobIds(defaultIds);
    compareColumnInitKeyRef.current = currentRunId;
  }, [loadingSummaries, allSummaries, currentRunId]);

  useEffect(() => {
    setExecutionsTablePage(1);
  }, [currentRunId]);

  useEffect(() => {
    const maxPage = Math.max(1, Math.ceil(allSummaries.length / EXECUTIONS_TABLE_PAGE_SIZE));
    setExecutionsTablePage((p) => Math.min(p, maxPage));
  }, [allSummaries.length]);

  const toggleCompareColumnSelection = useCallback((jobId: number) => {
    const id = Number(jobId);
    setSelectedCompareColumnJobIds((prev) => {
      const normalized = prev.map(Number);
      if (normalized.includes(id)) {
        return normalized.filter((j) => j !== id);
      }
      if (normalized.length >= MAX_COMPARE_COLUMNS) {
        alert('Máximo 4 escenarios para la vista en columnas.');
        return prev;
      }
      return [...normalized, id];
    });
  }, []);

  const clearCompareColumnSelection = useCallback(() => {
    setSelectedCompareColumnJobIds([]);
  }, []);

  /** ≥2 jobs marcados en la tabla comparativa → misma selección para gráficos en modo facet. */
  const columnCompareJobIds = useMemo(
    () => selectedCompareColumnJobIds.map(Number).filter((id) => !Number.isNaN(id) && id > 0),
    [selectedCompareColumnJobIds],
  );
  const facetFromCompareTable = columnCompareJobIds.length >= 2;
  const chartCompareMode: CompareMode = facetFromCompareTable ? 'facet' : compareState.mode;
  const chartJobIds = useMemo(() => {
    if (facetFromCompareTable) return columnCompareJobIds;
    if (compareState.jobIds.length > 0) return compareState.jobIds;
    return [currentRunId];
  }, [facetFromCompareTable, columnCompareJobIds, compareState.jobIds, currentRunId]);
  const chartYearsToPlot = compareState.yearsToPlot;

  const showFacetPlacementControl =
    chartCompareMode === 'facet' && chartJobIds.length > 1;

  // 3. Fetch chart data when selection or comparison changes
  useEffect(() => {
    if (!chartSelection.tipo) return;
    if (chartJobIds.length === 0) return;

    setLoadingChart(true);
    const isCompare = chartCompareMode !== 'off' && chartJobIds.length > 1;

    if (isCompare && chartCompareMode === 'facet') {
      const params: Record<string, string> = {
        job_ids: chartJobIds.join(','),
        tipo: chartSelection.tipo,
        un: chartSelection.un,
      };
      if (chartSelection.sub_filtro) params.sub_filtro = chartSelection.sub_filtro;
      if (chartSelection.loc) params.loc = chartSelection.loc;
      if (chartSelection.variable) params.variable = chartSelection.variable;
      if (chartSelection.agrupar_por) params.agrupar_por = chartSelection.agrupar_por;

      simulationApi
        .getCompareFacetData(params as Parameters<typeof simulationApi.getCompareFacetData>[0])
        .then((data: CompareChartFacetResponse) => {
          setCompareFacetData(data);
          setCompareChartData(null);
          setSingleChartData(null);
        })
        .catch((err: unknown) => console.error('Error loading compare-facet data', err))
        .finally(() => setLoadingChart(false));
    } else if (isCompare && chartCompareMode === 'by-year') {
      const params: Record<string, string> = {
        job_ids: chartJobIds.join(','),
        tipo: chartSelection.tipo,
        un: chartSelection.un,
        years_to_plot: chartYearsToPlot.join(','),
      };
      if (chartSelection.sub_filtro) params.sub_filtro = chartSelection.sub_filtro;
      if (chartSelection.loc) params.loc = chartSelection.loc;
      if (chartSelection.agrupar_por) params.agrupacion = chartSelection.agrupar_por;

      simulationApi
        .getCompareData(params as Parameters<typeof simulationApi.getCompareData>[0])
        .then((data: CompareChartResponse) => {
          setCompareChartData(data);
          setCompareFacetData(null);
          setSingleChartData(null);
        })
        .catch((err: unknown) => console.error('Error loading compare data', err))
        .finally(() => setLoadingChart(false));
    } else {
      const params: Record<string, string> = {
        tipo: chartSelection.tipo,
        un: chartSelection.un,
      };
      if (chartSelection.sub_filtro) params.sub_filtro = chartSelection.sub_filtro;
      if (chartSelection.loc) params.loc = chartSelection.loc;
      if (chartSelection.variable) params.variable = chartSelection.variable;
      if (chartSelection.agrupar_por) params.agrupar_por = chartSelection.agrupar_por;

      simulationApi
        .getChartData(
          currentRunId,
          params as Parameters<typeof simulationApi.getChartData>[1],
        )
        .then((data: ChartDataResponse) => {
          setSingleChartData(data);
          setCompareChartData(null);
          setCompareFacetData(null);
        })
        .catch((err: unknown) => console.error('Error loading chart data', err))
        .finally(() => setLoadingChart(false));
    }
  }, [currentRunId, chartSelection, chartCompareMode, chartJobIds, chartYearsToPlot]);

  // Toggle compare on/off
  const handleToggleCompare = useCallback(() => {
    setCompareState((prev) => {
      if (prev.mode !== 'off') {
        if (selectedCompareColumnJobIdsRef.current.length >= 2) {
          queueMicrotask(() => setSelectedCompareColumnJobIds([currentRunId]));
        }
        return { mode: 'off', jobIds: [currentRunId], yearsToPlot: prev.yearsToPlot };
      }
      const cols = selectedCompareColumnJobIdsRef.current.map(Number).filter((id) => id > 0);
      return {
        mode: 'facet',
        jobIds: cols.length >= 2 ? cols : prev.jobIds,
        yearsToPlot: prev.yearsToPlot,
      };
    });
  }, [currentRunId]);

  const handleCompareChange = useCallback(
    (selection: {
      jobIds: number[];
      yearsToPlot: number[];
      compareViewMode?: CompareViewMode;
    }) => {
      if (selectedCompareColumnJobIdsRef.current.length >= 2) {
        setSelectedCompareColumnJobIds(selection.jobIds.slice(0, MAX_COMPARE_COLUMNS));
      }
      setCompareState((prev) => {
        const newMode: CompareMode =
          prev.mode === 'off'
            ? prev.mode
            : (selection.compareViewMode ?? (prev.mode === 'by-year' ? 'by-year' : 'facet'));
        return {
          mode: newMode,
          jobIds: selection.jobIds,
          yearsToPlot: selection.yearsToPlot,
        };
      });
    },
    [],
  );

  // Cerrar dropdown al hacer clic fuera
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target as Node)) {
        setShowExportMenu(false);
      }
    };
    if (showExportMenu) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showExportMenu]);

  const handleExportSvg = useCallback(async () => {
    setShowExportMenu(false);
    setExportingType('svg');
    try {
      const response = await simulationApi.exportAllCharts(currentRunId, chartSelection.un);
      const blob = new Blob([response.data], {
        type: 'application/zip',
      });
      const disposition = response.headers['content-disposition'] || '';
      const match = disposition.match(/filename="?([^"]+)"?/);
      const filename = match?.[1] || `Graficas_${currentRunId}_${chartSelection.un}.zip`;
      downloadBlob(blob, filename);
    } catch (err) {
      console.error('Error exporting charts', err);
      alert('Error al generar el archivo. Intenta de nuevo.');
    } finally {
      setExportingType(null);
    }
  }, [currentRunId, chartSelection.un]);

  const handleExportExcel = useCallback(async () => {
    setShowExportMenu(false);
    setExportingType('excel');
    try {
      const { blob, filename } = await simulationApi.exportRawData(currentRunId);
      downloadBlob(blob, filename);
    } catch (err: unknown) {
      console.error('Error exporting raw data', err);
      let msg = 'Error descargando los datos crudos.';
      // ApiError normalizado (el interceptor convierte respuestas blob a mensaje genérico)
      if (err && typeof err === 'object' && 'message' in err && typeof (err as { message: string }).message === 'string') {
        msg = (err as { message: string }).message;
      }
      // Si el backend devolvió JSON en un Blob (responseType: blob), intentar extraer detail
      if (err && typeof err === 'object' && 'details' in err) {
        const details = (err as { details?: { response?: unknown } }).details;
        const resp = details?.response;
        if (resp instanceof Blob && resp.type.includes('json')) {
          try {
            const text = await resp.text();
            const parsed = JSON.parse(text);
            if (typeof parsed.detail === 'string') msg = parsed.detail;
          } catch {
            /* ignored */
          }
        }
      }
      alert(msg);
    } finally {
      setExportingType(null);
    }
  }, [currentRunId]);

  if (error) {
    return (
      <div className="p-8 text-center">
        <h2 className="text-xl font-bold text-red-400 mb-4">Error</h2>
        <p className="text-slate-400">{error}</p>
        <Link
          to="/app/results"
          className="text-blue-400 hover:underline mt-4 inline-block"
        >
          Volver a Resultados
        </Link>
      </div>
    );
  }

  const selectedCardsGridClass =
    scenarioCardsViewMode === 'list'
      ? 'flex flex-col gap-3'
      : 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4';

  const executionsTotalPages = Math.max(
    1,
    Math.ceil(allSummaries.length / EXECUTIONS_TABLE_PAGE_SIZE),
  );
  const executionsPageSafe = Math.min(executionsTablePage, executionsTotalPages);
  const executionsSliceStart = (executionsPageSafe - 1) * EXECUTIONS_TABLE_PAGE_SIZE;
  const paginatedSummaries = allSummaries.slice(
    executionsSliceStart,
    executionsSliceStart + EXECUTIONS_TABLE_PAGE_SIZE,
  );
  const executionsRangeEnd = Math.min(
    executionsSliceStart + EXECUTIONS_TABLE_PAGE_SIZE,
    allSummaries.length,
  );

  /** Evita duplicar la misma tarjeta KPI arriba y en "KPIs seleccionados" cuando ya hay selección en la comparativa. */
  const showHeroKpiCard =
    Boolean(summary) &&
    (loadingSummaries || allSummaries.length === 0 || selectedCompareColumnJobIds.length === 0);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 p-6 space-y-6 font-sans">
      {/* ─── HEADER ─── */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Resultados de simulación
          </h1>
          <p className="text-sm text-slate-500 mt-1 font-mono">#{currentRunId}</p>
        </div>
        <div className="flex gap-3 items-center flex-wrap">
          {isOptimal ? (
            <div ref={exportMenuRef} className="relative">
              <button
                type="button"
                onClick={() => setShowExportMenu((v) => !v)}
                disabled={exportingType !== null}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900/50 px-4 py-2 text-sm font-medium text-slate-200 backdrop-blur-sm hover:border-slate-600 hover:bg-slate-900 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {exportingType ? (
                  <>
                    <div className="w-4 h-4 rounded-full border-2 border-current/30 border-t-current animate-spin" />
                    {exportingType === 'svg' ? 'Generando ZIP…' : 'Generando Excel…'}
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Exportar
                    <svg className={`w-4 h-4 shrink-0 transition-transform ${showExportMenu ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                  </>
                )}
              </button>
              {showExportMenu && (
                <div className="absolute right-0 top-full mt-2 flex flex-col gap-1 min-w-[240px] rounded-xl border border-slate-800 bg-slate-900/95 p-2 shadow-xl backdrop-blur-md z-50">
                  <button
                    type="button"
                    onClick={handleExportSvg}
                    className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm text-slate-200 hover:bg-slate-800/80"
                  >
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-emerald-500/20 bg-emerald-500/10 text-emerald-400">
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                      </svg>
                    </span>
                    Gráficos (SVG / ZIP)
                  </button>
                  <button
                    type="button"
                    onClick={handleExportExcel}
                    className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm text-slate-200 hover:bg-slate-800/80"
                  >
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-cyan-500/20 bg-cyan-500/10 text-cyan-400">
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                    </span>
                    Datos crudos (Excel)
                  </button>
                </div>
              )}
            </div>
          ) : null}

          <Link to="/app/results">
            <Button
              variant="ghost"
              className="text-slate-300 hover:text-white hover:bg-slate-800/80 border border-slate-800 text-sm rounded-lg"
            >
              ← Volver a tabla
            </Button>
          </Link>
        </div>
      </div>

      {/* ─── RESUMEN KPI (solo si no está ya cubierto por la zona de comparativa seleccionada) ─── */}
      {loadingSummary ? (
        <div className="animate-pulse rounded-xl border border-slate-800 bg-[#0f172a]/80 h-44" />
      ) : summary && showHeroKpiCard ? (
        <ScenarioCard summary={summary} isCurrent />
      ) : null}

      {isNonOptimal ? (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-6 flex flex-wrap items-center justify-between gap-4">
          <div className="grid gap-2 text-sm text-rose-100/90 max-w-3xl">
            <strong className="text-rose-50">
              {hasInfeasibilityDetails
                ? 'Esta simulación reporta infactibilidad o un estado no óptimo.'
                : 'Esta simulación no terminó con una solución óptima.'}
            </strong>
            <span className="text-slate-400">
              Estado del solver:{' '}
              <span className="font-mono font-semibold text-slate-200 uppercase">
                {summary?.solver_name?.toUpperCase() ?? runResult?.solver_name?.toUpperCase() ?? 'SOLVER'}{' '}
                {(summary?.solver_status ?? runResult?.solver_status ?? 'unknown').toUpperCase()}
              </span>
            </span>
            {failureMessage ? <span className="text-slate-400">Detalle: {failureMessage}</span> : null}
            {!hasInfeasibilityDetails ? (
              <span className="text-slate-500 text-xs">
                No se pudieron recopilar diagnósticos detallados. Esto suele pasar cuando el worker se
                termina de forma abrupta antes de persistir la infactibilidad.
              </span>
            ) : (
              <span className="text-slate-500 text-xs">
                El análisis detallado (IIS + mapeo a parámetros) se ejecuta bajo demanda;
                usa el botón a la derecha para lanzarlo o ver su estado.
              </span>
            )}
          </div>
          {hasInfeasibilityDetails && runResult?.job_id ? (
            (() => {
              const solver = (runResult.solver_name ?? '').toLowerCase();
              const diag = runResult.infeasibility_diagnostics ?? null;
              // Retrocompat: jobs antiguos no tienen `diagnostic_status` pero sí
              // el reporte enriquecido; los tratamos como SUCCEEDED.
              const hasEnriched = Boolean(
                diag?.iis ||
                  diag?.overview ||
                  (diag?.top_suspects?.length ?? 0) > 0 ||
                  (diag?.constraint_analyses?.length ?? 0) > 0,
              );
              const diagStatus =
                diag?.diagnostic_status ?? (hasEnriched ? 'SUCCEEDED' : 'NONE');
              if (solver !== 'highs') {
                return (
                  <span className="text-xs text-slate-400 italic shrink-0 max-w-xs">
                    Para correr el diagnóstico de infactibilidad (IIS + mapeo a
                    parámetros) es necesario volver a lanzar la simulación con HiGHS.
                  </span>
                );
              }
              if (diagStatus === 'SUCCEEDED') {
                return (
                  <Link
                    to={paths.infeasibilityReport(runResult.job_id)}
                    className="bg-rose-600 hover:bg-rose-500 text-white border border-rose-500/50 rounded-lg shrink-0 px-4 py-2 font-semibold no-underline"
                  >
                    ⚠ Ver reporte de infactibilidad
                  </Link>
                );
              }
              if (diagStatus === 'QUEUED' || diagStatus === 'RUNNING') {
                return (
                  <Link
                    to={paths.infeasibilityReport(runResult.job_id)}
                    className="bg-amber-600/20 hover:bg-amber-600/30 text-amber-200 border border-amber-500/50 rounded-lg shrink-0 px-4 py-2 font-semibold no-underline"
                  >
                    {diagStatus === 'QUEUED'
                      ? 'Diagnóstico en cola…'
                      : 'Diagnosticando…'}
                  </Link>
                );
              }
              // NONE / FAILED → link a la página donde se lanza
              return (
                <Link
                  to={paths.infeasibilityReport(runResult.job_id)}
                  className="bg-rose-600 hover:bg-rose-500 text-white border border-rose-500/50 rounded-lg shrink-0 px-4 py-2 font-semibold no-underline"
                >
                  {diagStatus === 'FAILED'
                    ? '⚠ Reintentar diagnóstico'
                    : '⚠ Correr diagnóstico de infactibilidad'}
                </Link>
              );
            })()
          ) : null}
        </div>
      ) : null}

      {/* ─── COMPARATIVA ─── */}
      {!loadingSummaries && allSummaries.length > 0 && (
        <section className="rounded-xl border border-slate-800 bg-slate-900/30 backdrop-blur-sm overflow-hidden">
          <div className="p-6 border-b border-slate-800 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-1">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500">
                Comparativa de escenarios
              </h2>
              <p className="text-sm text-slate-500 m-0 max-w-2xl">
                Selecciona hasta {MAX_COMPARE_COLUMNS} ejecuciones. Con dos o más, los gráficos comparan esos jobs (una faceta por escenario).
              </p>
            </div>
            {selectedCompareColumnJobIds.length > 0 ? (
              <Button
                type="button"
                variant="ghost"
                className="text-slate-400 hover:text-white border border-slate-800 text-xs shrink-0 rounded-lg"
                onClick={clearCompareColumnSelection}
              >
                Limpiar selección
              </Button>
            ) : null}
          </div>

          {selectedCompareColumnJobIds.length > 0 ? (
            <div className="border-b border-slate-800 bg-slate-950/30">
              <div className="p-6 pb-0 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <p className="m-0 text-xs font-semibold uppercase tracking-[0.08em] text-slate-400">
                  KPIs seleccionados ({selectedCompareColumnJobIds.length})
                </p>
                <div
                  className="inline-flex shrink-0 rounded-lg border border-slate-700/80 bg-slate-900/70 p-0.5"
                  role="group"
                  aria-label="Modo de vista de tarjetas"
                >
                  <button
                    type="button"
                    onClick={() => setScenarioCardsViewMode('grid')}
                    className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-xs font-semibold transition-colors ${
                      scenarioCardsViewMode === 'grid'
                        ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/20'
                        : 'text-slate-500 hover:text-slate-300'
                    }`}
                  >
                    <LayoutGrid className="h-4 w-4" aria-hidden />
                    Cuadrícula
                  </button>
                  <button
                    type="button"
                    onClick={() => setScenarioCardsViewMode('list')}
                    className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-xs font-semibold transition-colors ${
                      scenarioCardsViewMode === 'list'
                        ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/20'
                        : 'text-slate-500 hover:text-slate-300'
                    }`}
                  >
                    <List className="h-4 w-4" aria-hidden />
                    Lista
                  </button>
                </div>
              </div>
              <div className={`p-6 pt-4 ${selectedCardsGridClass}`}>
                {selectedCompareColumnJobIds.map((jobId) => {
                  const colSummary = allSummaries.find((x) => Number(x.job_id) === Number(jobId));
                  if (!colSummary) return null;
                  return (
                    <ScenarioCard
                      key={jobId}
                      summary={colSummary}
                      isCurrent={Number(colSummary.job_id) === Number(currentRunId)}
                    />
                  );
                })}
              </div>
            </div>
          ) : null}

          <details open className="border-t border-slate-800">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-6 py-4 text-sm font-medium text-slate-400 transition-colors hover:text-slate-200 [&::-webkit-details-marker]:hidden">
              <span>Tabla de ejecuciones</span>
              <span className="shrink-0 text-xs text-slate-600">
                Selección para comparar · {allSummaries.length} filas · {EXECUTIONS_TABLE_PAGE_SIZE} por página
              </span>
            </summary>
            <div className="overflow-x-auto border-t border-slate-800/80 px-0 pb-0">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800 bg-slate-950/50 text-left">
                    <th className="w-10 p-4 text-center">
                      <span className="sr-only">Comparar</span>
                    </th>
                    <th className="p-4 text-xs font-semibold uppercase tracking-wider text-slate-500">
                      Escenario
                    </th>
                    <th className="p-4 text-xs font-semibold uppercase tracking-wider text-slate-500">
                      Estado
                    </th>
                    <th className="p-4 text-right text-xs font-semibold uppercase tracking-wider text-slate-500">
                      Objective (USD)
                    </th>
                    <th className="p-4 text-right text-xs font-semibold uppercase tracking-wider text-slate-500">
                      Cobertura %
                    </th>
                    <th className="p-4 text-right text-xs font-semibold uppercase tracking-wider text-slate-500">
                      CO₂ (Mt)
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedSummaries.map((s) => {
                    const isCurrent = Number(s.job_id) === Number(currentRunId);
                    const isColSelected = selectedCompareColumnJobIds.map(Number).includes(Number(s.job_id));
                    const st = getSolverStatusPresentation(s.solver_status);
                    return (
                      <tr
                        key={s.job_id}
                        className={`border-b border-slate-800/80 transition-colors ${
                          isCurrent ? 'bg-emerald-500/[0.04]' : 'hover:bg-slate-900/50'
                        }`}
                      >
                        <td className="p-4 text-center align-middle">
                          <input
                            type="checkbox"
                            checked={isColSelected}
                            onChange={() => toggleCompareColumnSelection(Number(s.job_id))}
                            aria-label={`Incluir ${s.scenario_name || `Job ${s.job_id}`} en vista columnas`}
                            className="h-4 w-4 cursor-pointer rounded border-slate-600 bg-slate-950 text-emerald-500 focus:ring-emerald-500/40"
                          />
                        </td>
                        <td className="p-4">
                          <Link
                            to={`/app/results/${s.job_id}`}
                            className={`font-medium hover:text-emerald-400 hover:underline ${
                              isCurrent ? 'text-emerald-400' : 'text-slate-200'
                            }`}
                          >
                            {s.scenario_name || `Job #${s.job_id}`}
                            {isCurrent ? (
                              <span className="ml-2 rounded-md bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-400">
                                Actual
                              </span>
                            ) : null}
                          </Link>
                        </td>
                        <td className="p-4">
                          <span className={st.badgeClass}>{st.label}</span>
                        </td>
                        <td className="p-4 text-right font-mono text-slate-200 tabular-nums">
                          {formatCompactNumber(s.objective_value, 2)}
                        </td>
                        <td className="p-4 text-right font-mono text-slate-200 tabular-nums">
                          {formatPercent(s.coverage_ratio, 2)}
                        </td>
                        <td className="p-4 text-right font-mono text-slate-200 tabular-nums">
                          {formatCompactNumber(s.total_co2, 2)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-800/80 px-6 py-3">
                <p className="m-0 text-xs text-slate-500">
                  {allSummaries.length === 0
                    ? 'Sin filas'
                    : `${executionsSliceStart + 1}–${executionsRangeEnd} de ${allSummaries.length}`}
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    disabled={executionsPageSafe <= 1}
                    onClick={() => setExecutionsTablePage((p) => Math.max(1, p - 1))}
                    className="text-xs rounded-lg border border-slate-800 px-3 py-1.5 disabled:opacity-40"
                  >
                    Anterior
                  </Button>
                  <span className="text-xs tabular-nums text-slate-400">
                    Página {executionsPageSafe} / {executionsTotalPages}
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    disabled={executionsPageSafe >= executionsTotalPages}
                    onClick={() =>
                      setExecutionsTablePage((p) => Math.min(executionsTotalPages, p + 1))
                    }
                    className="text-xs rounded-lg border border-slate-800 px-3 py-1.5 disabled:opacity-40"
                  >
                    Siguiente
                  </Button>
                </div>
              </div>
            </div>
          </details>
        </section>
      )}

      {isOptimal ? (
        <>
          <div className="rounded-xl border border-slate-800 bg-slate-900/30 backdrop-blur-sm p-6 relative">
            {loadingChart && (
              <div className="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-slate-950/70 backdrop-blur-sm">
                <div className="flex flex-col items-center gap-3">
                  <div className="h-8 w-8 rounded-full border-2 border-slate-700 border-t-emerald-500 animate-spin" />
                  <span className="text-sm font-medium text-slate-400">Renderizando gráfico…</span>
                </div>
              </div>
            )}

            {chartCompareMode === 'facet' && chartJobIds.length > 1 && compareFacetData ? (
              <CompareChartFacet
                data={compareFacetData}
                barOrientation={chartBarOrientation}
                facetPlacement={chartFacetPlacement}
                legendMode={chartFacetLegendMode}
              />
            ) : chartCompareMode === 'by-year' && chartJobIds.length > 1 && compareChartData ? (
              <CompareChart data={compareChartData} barOrientation={chartBarOrientation} />
            ) : singleChartData ? (
              chartSelection.viewMode === 'line'
                ? (
                    <LineChart
                      data={singleChartData}
                      serverExport={{ jobId: currentRunId, selection: chartSelection }}
                    />
                  )
                : (
                    <HighchartsChart
                      data={singleChartData}
                      barOrientation={chartBarOrientation}
                      serverExport={{ jobId: currentRunId, selection: chartSelection }}
                    />
                  )
            ) : !loadingChart ? (
              <div className="flex h-[400px] flex-col items-center justify-center px-4 text-center text-slate-500">
                <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full border border-slate-800 bg-slate-900/50">
                  <svg className="h-8 w-8 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                <h3 className="mb-1 text-base font-medium text-slate-400">Sin datos para mostrar</h3>
                <p className="text-sm text-slate-600">Elige un tipo de gráfico en el panel inferior.</p>
              </div>
            ) : null}
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/30 backdrop-blur-sm p-6 space-y-6">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Configuración de gráfico
            </h3>

            <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4 space-y-4">
              <div>
                <p className="m-0 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">
                  Orientación de barras
                </p>
                <p className="mt-1 mb-3 text-xs text-slate-600">
                  Aplica a gráficos de barras apiladas (una ejecución, comparación por año o por escenario).
                  Las series en línea no cambian.
                </p>
                <div
                  className="inline-flex flex-wrap gap-2 rounded-lg border border-slate-800 bg-slate-900/60 p-0.5"
                  role="group"
                  aria-label="Orientación de barras"
                >
                  <button
                    type="button"
                    onClick={() => setChartBarOrientation('vertical')}
                    className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-xs font-semibold transition-colors ${
                      chartBarOrientation === 'vertical'
                        ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/25'
                        : 'text-slate-500 hover:text-slate-300 border border-transparent'
                    }`}
                  >
                    <BarChart3 className="h-4 w-4 shrink-0" aria-hidden />
                    Columnas (predeterminado)
                  </button>
                  <button
                    type="button"
                    onClick={() => setChartBarOrientation('horizontal')}
                    className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-xs font-semibold transition-colors ${
                      chartBarOrientation === 'horizontal'
                        ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/25'
                        : 'text-slate-500 hover:text-slate-300 border border-transparent'
                    }`}
                  >
                    <AlignLeft className="h-4 w-4 shrink-0" aria-hidden />
                    Barras horizontales
                  </button>
                </div>
              </div>

              <div>
                <p className="m-0 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">
                  Colocación de gráficas comparativas
                </p>
                <p className="mt-1 mb-3 text-xs text-slate-600">
                  Solo cuando comparas varios escenarios en modo una gráfica por escenario (facetas).
                </p>
                <div
                  className="inline-flex flex-wrap gap-2 rounded-lg border border-slate-800 bg-slate-900/60 p-0.5"
                  role="group"
                  aria-label="Colocación de facetas"
                >
                  <button
                    type="button"
                    disabled={!showFacetPlacementControl}
                    onClick={() => setChartFacetPlacement('inline')}
                    className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-xs font-semibold transition-colors disabled:opacity-50 ${
                      chartFacetPlacement === 'inline'
                        ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/25'
                        : 'text-slate-500 hover:text-slate-300 border border-transparent'
                    }`}
                  >
                    <GalleryHorizontal className="h-4 w-4 shrink-0" aria-hidden />
                    En fila (desplazamiento)
                  </button>
                  <button
                    type="button"
                    disabled={!showFacetPlacementControl}
                    onClick={() => setChartFacetPlacement('stacked')}
                    className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-xs font-semibold transition-colors disabled:opacity-50 ${
                      chartFacetPlacement === 'stacked'
                        ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/25'
                        : 'text-slate-500 hover:text-slate-300 border border-transparent'
                    }`}
                  >
                    <GalleryVertical className="h-4 w-4 shrink-0" aria-hidden />
                    Apiladas verticalmente
                  </button>
                </div>
              </div>

              <div>
                <p className="m-0 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">
                  Leyenda en comparación por escenario
                </p>
                <p className="mt-1 mb-3 text-xs text-slate-600">
                  Panel único arriba (recomendado) o leyenda de Highcharts solo en la primera gráfica.
                </p>
                <div
                  className="inline-flex flex-wrap gap-2 rounded-lg border border-slate-800 bg-slate-900/60 p-0.5"
                  role="group"
                  aria-label="Modo de leyenda en facetas"
                >
                  <button
                    type="button"
                    disabled={!showFacetPlacementControl}
                    onClick={() => setChartFacetLegendMode('shared')}
                    className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-xs font-semibold transition-colors disabled:opacity-50 ${
                      chartFacetLegendMode === 'shared'
                        ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/25'
                        : 'text-slate-500 hover:text-slate-300 border border-transparent'
                    }`}
                  >
                    <Layers className="h-4 w-4 shrink-0" aria-hidden />
                    Panel compartido
                  </button>
                  <button
                    type="button"
                    disabled={!showFacetPlacementControl}
                    onClick={() => setChartFacetLegendMode('perFacet')}
                    className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-xs font-semibold transition-colors disabled:opacity-50 ${
                      chartFacetLegendMode === 'perFacet'
                        ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/25'
                        : 'text-slate-500 hover:text-slate-300 border border-transparent'
                    }`}
                  >
                    <PanelBottom className="h-4 w-4 shrink-0" aria-hidden />
                    Solo primera gráfica
                  </button>
                </div>
              </div>
            </div>

            <ChartSelector value={chartSelection} onChange={setChartSelection} />
            <ScenarioComparer
              currentRunId={currentRunId}
              selectedJobIds={facetFromCompareTable ? columnCompareJobIds : compareState.jobIds}
              selectedYears={compareState.yearsToPlot}
              compareViewMode={compareState.mode === 'by-year' ? 'by-year' : 'facet'}
              enabled={facetFromCompareTable || compareState.mode !== 'off'}
              onToggle={handleToggleCompare}
              onChange={handleCompareChange}
            />
          </div>
        </>
      ) : null}
    </div>
  );
}
