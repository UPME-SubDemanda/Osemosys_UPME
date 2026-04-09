import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { simulationApi } from '../features/simulation/api/simulationApi';
import { scenariosApi } from '../features/scenarios/api/scenariosApi';
import type {
  ResultSummaryResponse,
  ChartDataResponse,
  CompareChartResponse,
  CompareChartFacetResponse,
  CompareMode,
  RunResult,
  SimulationRun,
} from '../types/domain';
import {
  InfeasibilityDiagnosticsPanel,
  type ScenarioParamsForDiagnostics,
} from '../features/simulation/components/InfeasibilityDiagnosticsPanel';
import { ChartSelector, type ChartSelection } from '../shared/charts/ChartSelector';
import { ScenarioComparer, type CompareViewMode } from '../shared/charts/ScenarioComparer';
import { HighchartsChart } from '../shared/charts/HighchartsChart';
import { LineChart } from '../shared/charts/LineChart';
import { CompareChart } from '../shared/charts/CompareChart';
import { CompareChartFacet } from '../shared/charts/CompareChartFacet';
import { Button } from '../shared/components/Button';
import { Modal } from '../shared/components/Modal';

export function ResultDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const currentRunId = Number(runId);

  // Summary & error
  const [summary, setSummary] = useState<ResultSummaryResponse | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runResult, setRunResult] = useState<RunResult | null>(null);
  const [runMeta, setRunMeta] = useState<SimulationRun | null>(null);
  const [scenarioParamsForDiagnostics, setScenarioParamsForDiagnostics] =
    useState<ScenarioParamsForDiagnostics>({ state: 'none' });

  // All summaries for comparison table
  const [allSummaries, setAllSummaries] = useState<ResultSummaryResponse[]>([]);
  const [loadingSummaries, setLoadingSummaries] = useState(true);

  // Chart selector
  const [chartSelection, setChartSelection] = useState<ChartSelection>({
    tipo: '',
    un: 'PJ',
    sub_filtro: '',
    loc: '',
    variable: '',
    viewMode: 'column',
    agrupar_por: 'TECNOLOGIA',
  });

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

  // Export state: 'svg' | 'excel' mientras se descarga, null si no
  const [exportingType, setExportingType] = useState<'svg' | 'excel' | null>(null);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [showInfeasibilityModal, setShowInfeasibilityModal] = useState(false);
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

  useEffect(() => {
    const sid = runResult?.scenario_id;
    if (sid == null || Number.isNaN(Number(sid))) {
      setScenarioParamsForDiagnostics({ state: 'none' });
      return;
    }
    let cancelled = false;
    setScenarioParamsForDiagnostics({ state: 'loading' });
    scenariosApi
      .getScenarioById(sid)
      .then((s) => {
        if (!cancelled) {
          setScenarioParamsForDiagnostics({
            state: 'loaded',
            names: s.changed_param_names ?? [],
          });
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setScenarioParamsForDiagnostics({
            state: 'error',
            message: err instanceof Error ? err.message : 'Error al cargar el escenario',
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [runResult?.scenario_id]);

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

  // 3. Fetch chart data when selection or comparison changes
  useEffect(() => {
    if (!chartSelection.tipo) return;
    const { mode, jobIds, yearsToPlot } = compareState;
    if (jobIds.length === 0) return;

    setLoadingChart(true);
    const isCompare = mode !== 'off' && jobIds.length > 1;

    if (isCompare && mode === 'facet') {
      const params: Record<string, string> = {
        job_ids: jobIds.join(','),
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
    } else if (isCompare && mode === 'by-year') {
      const params: Record<string, string> = {
        job_ids: jobIds.join(','),
        tipo: chartSelection.tipo,
        un: chartSelection.un,
        years_to_plot: yearsToPlot.join(','),
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
  }, [currentRunId, chartSelection, compareState]);

  // Toggle compare on/off
  const handleToggleCompare = useCallback(() => {
    setCompareState((prev) => {
      if (prev.mode !== 'off') {
        return { mode: 'off', jobIds: [currentRunId], yearsToPlot: prev.yearsToPlot };
      }
      return {
        mode: 'facet',
        jobIds: prev.jobIds,
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
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const disposition = response.headers['content-disposition'] || '';
      const match = disposition.match(/filename="?([^"]+)"?/);
      a.download = match?.[1] || `Graficas_${currentRunId}_${chartSelection.un}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
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
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
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

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-200 p-4 sm:p-6 lg:p-8 space-y-5 font-sans">
      {/* ─── HEADER ─── */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-white">
            Resultados de Simulacion
          </h1>
          <p className="text-sm text-slate-400 mt-0.5">
            #{currentRunId}
            {summary?.scenario_name ? ` — ${summary.scenario_name}` : ''}
          </p>
        </div>
        <div className="flex gap-3 items-center flex-wrap">
          {isOptimal ? (
            <div ref={exportMenuRef} className="relative">
              <button
                type="button"
                onClick={() => setShowExportMenu((v) => !v)}
                disabled={exportingType !== null}
                className="btn btn--primary inline-flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {exportingType ? (
                  <>
                    <div className="w-4 h-4 rounded-full border-2 border-current/30 border-t-current animate-spin" />
                    {exportingType === 'svg' ? 'Generando ZIP...' : 'Generando Excel...'}
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Exportar
                    <svg className={`w-4 h-4 transition-transform ${showExportMenu ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                  </>
                )}
              </button>
              {showExportMenu && (
                <div className="absolute right-0 top-full mt-2 flex flex-col gap-1.5 min-w-[240px] p-2 rounded-xl bg-[#1e293b]/95 border border-[rgba(255,255,255,0.1)] shadow-xl backdrop-blur-sm z-50">
                  <button
                    type="button"
                    onClick={handleExportSvg}
                    className="btn btn--ghost justify-start gap-3 px-4 py-3 text-sm w-full"
                  >
                    <span className="w-8 h-8 rounded-lg flex items-center justify-center bg-emerald-500/15 text-emerald-400 shrink-0 border border-emerald-500/20">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                      </svg>
                    </span>
                    <span>Graficos y Resultados (SVG/ZIP)</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleExportExcel}
                    className="btn btn--ghost justify-start gap-3 px-4 py-3 text-sm w-full"
                  >
                    <span className="w-8 h-8 rounded-lg flex items-center justify-center bg-blue-500/15 text-blue-400 shrink-0 border border-blue-500/20">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                    </span>
                    <span>Datos crudos (Excel)</span>
                  </button>
                </div>
              )}
            </div>
          ) : null}

          <Link to="/app/results">
            <Button
              variant="ghost"
              className="text-slate-300 hover:text-white hover:bg-slate-800 border border-slate-700 text-sm"
            >
              &larr; Volver a Tabla
            </Button>
          </Link>
        </div>
      </div>

      {/* ─── KPI CARDS ─── */}
      {loadingSummary ? (
        <div className="animate-pulse bg-[#1e293b] h-24 rounded-xl border border-slate-700/50" />
      ) : summary ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <KpiCard
            label="Estado del Solver"
            value={`${summary.solver_name.toUpperCase()} ${summary.solver_status.toUpperCase()}`}
            colorClass={
              summary.solver_status.toLowerCase().includes('optimal')
                ? 'text-emerald-400'
                : 'text-amber-400'
            }
            borderColor={
              summary.solver_status.toLowerCase().includes('optimal')
                ? 'border-t-emerald-400'
                : 'border-t-amber-400'
            }
          />
          <KpiCard
            label="Valor Objetivo"
            value={summary.objective_value.toLocaleString(undefined, {
              maximumFractionDigits: 2,
            })}
            colorClass="text-blue-400"
            borderColor="border-t-blue-400"
          />
          <KpiCard
            label="Cobertura de Demanda"
            value={`${(summary.coverage_ratio * 100).toFixed(2)}%`}
            colorClass="text-amber-400"
            borderColor="border-t-amber-400"
          />
          <KpiCard
            label="Emisiones CO2 (MtCO₂eq)"
            value={summary.total_co2.toLocaleString(undefined, {
              maximumFractionDigits: 2,
            })}
            colorClass="text-rose-400"
            borderColor="border-t-rose-400"
          />
        </div>
      ) : null}

      {isNonOptimal ? (
        <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 flex flex-wrap items-center justify-between gap-3">
          <div className="grid gap-1 text-sm text-red-100">
            <strong className="text-red-50">
              {hasInfeasibilityDetails
                ? 'Esta simulación reporta infactibilidad o un estado no óptimo.'
                : 'Esta simulación no terminó con una solución óptima.'}
            </strong>
            <span>
              Estado del solver:{' '}
              <span className="font-semibold uppercase">
                {summary?.solver_name?.toUpperCase() ?? runResult?.solver_name?.toUpperCase() ?? 'SOLVER'}{' '}
                {(summary?.solver_status ?? runResult?.solver_status ?? 'unknown').toUpperCase()}
              </span>
            </span>
            {failureMessage ? <span>Detalle: {failureMessage}</span> : null}
            {!hasInfeasibilityDetails ? (
              <span>
                No se pudieron recopilar diagnósticos detallados. Esto suele pasar cuando el worker se
                termina de forma abrupta antes de persistir la infactibilidad.
              </span>
            ) : (
              <span>
                Puedes abrir el diagnóstico detallado para revisar restricciones violadas y conflictos
                de bounds.
              </span>
            )}
          </div>
          {hasInfeasibilityDetails ? (
            <Button
              type="button"
              onClick={() => setShowInfeasibilityModal(true)}
              className="bg-red-600 hover:bg-red-500 text-white border border-red-500"
            >
              Ver diagnóstico de infactibilidad
            </Button>
          ) : null}
        </div>
      ) : null}

      <Modal
        open={showInfeasibilityModal}
        onClose={() => setShowInfeasibilityModal(false)}
        title="Diagnóstico de infactibilidad"
        wide
      >
        {hasInfeasibilityDetails && runResult ? (
          <InfeasibilityDiagnosticsPanel
            result={runResult}
            scenarioParams={scenarioParamsForDiagnostics}
            scenarioId={runResult.scenario_id ?? null}
          />
        ) : null}
      </Modal>

      {/* ─── COMPARISON TABLE ─── */}
      {!loadingSummaries && allSummaries.length > 0 && (
        <div className="bg-[#1e293b] rounded-xl border border-slate-700/50 overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-700/50">
            <h3 className="text-xs font-bold uppercase tracking-wide text-slate-400">
              Comparativa de Escenarios
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700/50 text-left">
                  <th className="px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
                    Escenario
                  </th>
                  <th className="px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
                    Solver State
                  </th>
                  <th className="px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-400 text-right">
                    Objective Value (USD)
                  </th>
                  <th className="px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-400 text-right">
                    Demand Coverage (%)
                  </th>
                  <th className="px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-400 text-right">
                    CO2 Emissions (MtCO₂eq)
                  </th>
                </tr>
              </thead>
              <tbody>
                {allSummaries.map((s) => {
                  const isCurrent = s.job_id === currentRunId;
                  return (
                    <tr
                      key={s.job_id}
                      className={`border-b border-slate-800 transition-colors ${
                        isCurrent
                          ? 'bg-blue-500/5'
                          : 'hover:bg-slate-800/40'
                      }`}
                    >
                      <td className="px-4 py-2.5">
                        <Link
                          to={`/app/results/${s.job_id}`}
                          className={`hover:underline ${isCurrent ? 'text-blue-400 font-medium' : 'text-slate-300'}`}
                        >
                          {s.scenario_name || `Job #${s.job_id}`}
                          {isCurrent && (
                            <span className="ml-1.5 text-[10px] bg-blue-500/10 text-blue-400 px-1.5 py-0.5 rounded">
                              Actual
                            </span>
                          )}
                        </Link>
                      </td>
                      <td className="px-4 py-2.5">
                        <span
                          className={`text-xs font-semibold uppercase ${
                            s.solver_status.toLowerCase().includes('optimal')
                              ? 'text-emerald-400'
                              : 'text-amber-400'
                          }`}
                        >
                          {s.solver_status.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right text-slate-300 tabular-nums">
                        {s.objective_value.toLocaleString(undefined, {
                          maximumFractionDigits: 2,
                        })}
                      </td>
                      <td className="px-4 py-2.5 text-right text-slate-300 tabular-nums">
                        {(s.coverage_ratio * 100).toFixed(2)}%
                      </td>
                      <td className="px-4 py-2.5 text-right text-slate-300 tabular-nums">
                        {s.total_co2.toLocaleString(undefined, {
                          maximumFractionDigits: 2,
                        })}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {isOptimal ? (
        <>
          {/* ─── CHART ─── */}
          <div className="bg-[#1e293b] p-4 rounded-xl border border-slate-700/50 relative">
            {loadingChart && (
              <div className="absolute inset-0 z-10 bg-[#1e293b]/80 backdrop-blur-sm flex items-center justify-center rounded-xl">
                <div className="flex flex-col items-center">
                  <div className="w-7 h-7 rounded-full border-4 border-slate-600 border-t-blue-500 animate-spin mb-3" />
                  <span className="text-blue-400 text-sm font-medium">Renderizando grafica...</span>
                </div>
              </div>
            )}

            {compareState.mode === 'facet' && compareState.jobIds.length > 1 && compareFacetData ? (
              <CompareChartFacet data={compareFacetData} />
            ) : compareState.mode === 'by-year' && compareState.jobIds.length > 1 && compareChartData ? (
              <CompareChart data={compareChartData} />
            ) : singleChartData ? (
              chartSelection.viewMode === 'line'
                ? <LineChart data={singleChartData} />
                : <HighchartsChart data={singleChartData} />
            ) : !loadingChart ? (
              <div className="h-[400px] flex flex-col items-center justify-center text-slate-500 text-center px-4">
                <div className="w-16 h-16 mb-3 rounded-full bg-slate-800 flex items-center justify-center">
                  <svg
                    className="w-8 h-8 text-slate-600"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                    />
                  </svg>
                </div>
                <h3 className="text-base font-medium text-slate-400 mb-1">No hay datos para mostrar</h3>
                <p className="text-sm">Selecciona una grafica en el panel inferior.</p>
              </div>
            ) : null}
          </div>

          {/* ─── CONFIGURATION ─── */}
          <div className="bg-[#1e293b] p-4 rounded-xl border border-slate-700/50">
            <h3 className="text-xs font-bold uppercase tracking-wide text-slate-400 mb-3">
              Configuracion de Grafica
            </h3>
            <ChartSelector value={chartSelection} onChange={setChartSelection} />
            {/* ─── COMPARE TOGGLE + SCENARIO COMPARER ─── */}
            <ScenarioComparer
              currentRunId={currentRunId}
              selectedJobIds={compareState.jobIds}
              selectedYears={compareState.yearsToPlot}
              compareViewMode={compareState.mode === 'by-year' ? 'by-year' : 'facet'}
              enabled={compareState.mode !== 'off'}
              onToggle={handleToggleCompare}
              onChange={handleCompareChange}
            />
          </div>
        </>
      ) : null}
    </div>
  );
}

/* ─── KPI Card sub-component ─── */
function KpiCard({
  label,
  value,
  colorClass,
  borderColor,
}: {
  label: string;
  value: string;
  colorClass: string;
  borderColor: string;
}) {
  return (
    <div className={`bg-[#1e293b] px-5 py-4 rounded-xl shadow-lg border-t-4 border-x border-b border-slate-700/50 flex flex-col justify-center ${borderColor}`}>
      <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 mb-1">
        {label}
      </dt>
      <dd className={`text-xl font-bold tracking-tight ${colorClass}`}>{value}</dd>
    </div>
  );
}
