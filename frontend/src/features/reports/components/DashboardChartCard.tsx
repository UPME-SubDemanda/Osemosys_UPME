/**
 * Tarjeta de gráfica para el dashboard del reporte:
 *   - Resuelve job_ids slot-a-slot desde los escenarios globales.
 *   - Pide los datos al backend (chart-data o compare-facet) según
 *     `template.compare_mode`.
 *   - Renderiza con `HighchartsChart` o `CompareChartFacet`.
 *   - Indica claramente cuando faltan escenarios o no hay datos.
 */
import { useEffect, useMemo, useState } from "react";
import { simulationApi } from "@/features/simulation/api/simulationApi";
import { HighchartsChart } from "@/shared/charts/HighchartsChart";
import { CompareChart } from "@/shared/charts/CompareChart";
import { CompareChartFacet } from "@/shared/charts/CompareChartFacet";
import { LineChart } from "@/shared/charts/LineChart";
import { ParetoChart } from "@/shared/charts/ParetoChart";
import type {
  ChartDataResponse,
  CompareChartFacetResponse,
  CompareChartResponse,
  ParetoChartResponse,
  SavedChartTemplate,
} from "@/types/domain";
import type { ChartSelection } from "@/shared/charts/ChartSelector";

function templateToSelection(t: SavedChartTemplate): ChartSelection {
  const sel: ChartSelection = { tipo: t.tipo, un: t.un };
  if (t.sub_filtro) sel.sub_filtro = t.sub_filtro;
  if (t.loc) sel.loc = t.loc;
  if (t.variable) sel.variable = t.variable;
  if (t.agrupar_por) sel.agrupar_por = t.agrupar_por;
  if (t.view_mode) sel.viewMode = t.view_mode;
  return sel;
}

type Props = {
  template: SavedChartTemplate;
  jobIds: number[];
  /** Si true, los controles del facet se compactan en un menú "⋯". */
  compactToolbar?: boolean;
  /**
   * Sufijo a agregar al título cuando la gráfica de un solo escenario vive en
   * un reporte multi-escenario (e.g. "Alto", "Bajo"). El componente antepone
   * " — " automáticamente.
   */
  scenarioAliasSuffix?: string | undefined;
  /**
   * Nombres (alias) a usar por escenario, paralelos a `jobIds`. Se aplican
   * como override al nombre/leyenda de series/facets en multi-escenario.
   */
  scenarioNames?: string[] | undefined;
};

export function DashboardChartCard({
  template,
  jobIds,
  compactToolbar = false,
  scenarioAliasSuffix,
  scenarioNames,
}: Props) {
  const [single, setSingle] = useState<ChartDataResponse | null>(null);
  const [facet, setFacet] = useState<CompareChartFacetResponse | null>(null);
  const [byYear, setByYear] = useState<CompareChartResponse | null>(null);
  const [lineTotal, setLineTotal] = useState<ChartDataResponse | null>(null);
  const [pareto, setPareto] = useState<ParetoChartResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ready =
    jobIds.length === template.num_scenarios && jobIds.every((j) => j != null);

  // Fingerprint estable para evitar re-fetch redundante.
  const fingerprint = `${template.id}|${template.compare_mode}|${jobIds.join(",")}|${(template.years_to_plot ?? []).join(",")}`;

  useEffect(() => {
    if (!ready) {
      setSingle(null);
      setFacet(null);
      setByYear(null);
      setLineTotal(null);
      setPareto(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);

    const reportTitleOverride = template.report_title?.trim() || null;
    const suffix = scenarioAliasSuffix?.trim() || null;
    const applyTitle = <T extends { title?: string | null }>(d: T): T => {
      const base = reportTitleOverride ?? (d.title ?? "");
      const finalTitle = suffix ? `${base} — ${suffix}` : base;
      if (reportTitleOverride || suffix) {
        (d as { title?: string }).title = finalTitle;
      }
      return d;
    };
    /** Aplica los aliases (paralelos a jobIds) al nombre de series/facets. */
    const aliasOf = (i: number): string | null => {
      const v = scenarioNames?.[i]?.trim();
      return v && v.length > 0 ? v : null;
    };
    const applyFacetAliases = (d: CompareChartFacetResponse) => {
      d.facets = d.facets.map((f, i) => {
        const a = aliasOf(i);
        return a
          ? {
              ...f,
              display_name: a,
              scenario_name: a,
              // Cuando el alias reemplaza el nombre del escenario, limpiamos
              // la etiqueta para que el subtítulo quede "Alias" y no "Alias — Tag".
              scenario_tag_name: null,
            }
          : f;
      });
      return d;
    };
    const applySeriesAliases = <T extends { series: { name: string }[] }>(d: T): T => {
      d.series = d.series.map((s, i) => {
        const a = aliasOf(i);
        return a ? { ...s, name: a } : s;
      });
      return d;
    };
    const applyByYearAliases = (d: CompareChartResponse): CompareChartResponse => {
      d.subplots = d.subplots.map((sub) => ({
        ...sub,
        series: sub.series.map((s, i) => {
          const a = aliasOf(i);
          return a ? { ...s, name: a } : s;
        }),
      }));
      return d;
    };

    if (template.view_mode === "pareto" && template.compare_mode === "off") {
      const params: Record<string, string> = {
        tipo: template.tipo,
        un: template.un,
      };
      if (template.sub_filtro) params.sub_filtro = template.sub_filtro;
      if (template.loc) params.loc = template.loc;
      const jobId = jobIds[0]!;
      simulationApi
        .getParetoData(
          jobId,
          params as Parameters<typeof simulationApi.getParetoData>[1],
        )
        .then((data) => {
          if (cancelled) return;
          setPareto(applyTitle(data));
          setSingle(null);
          setFacet(null);
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          setError(err instanceof Error ? err.message : "Error cargando gráfica.");
        })
        .finally(() => !cancelled && setLoading(false));
      return () => {
        cancelled = true;
      };
    }

    if (template.compare_mode === "facet") {
      const params: Record<string, string> = {
        job_ids: jobIds.join(","),
        tipo: template.tipo,
        un: template.un,
      };
      if (template.sub_filtro) params.sub_filtro = template.sub_filtro;
      if (template.loc) params.loc = template.loc;
      if (template.variable) params.variable = template.variable;
      if (template.agrupar_por) params.agrupar_por = template.agrupar_por;
      simulationApi
        .getCompareFacetData(
          params as Parameters<typeof simulationApi.getCompareFacetData>[0],
        )
        .then((data) => {
          if (cancelled) return;
          setFacet(applyTitle(applyFacetAliases(data)));
          setSingle(null);
          setByYear(null);
          setLineTotal(null);
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          setError(err instanceof Error ? err.message : "Error cargando gráfica.");
        })
        .finally(() => !cancelled && setLoading(false));
    } else if (template.compare_mode === "by-year") {
      const params: Record<string, string> = {
        job_ids: jobIds.join(","),
        tipo: template.tipo,
        un: template.un,
        years_to_plot: (template.years_to_plot ?? []).join(","),
      };
      if (template.sub_filtro) params.sub_filtro = template.sub_filtro;
      if (template.loc) params.loc = template.loc;
      if (template.agrupar_por) params.agrupacion = template.agrupar_por;
      simulationApi
        .getCompareData(
          params as Parameters<typeof simulationApi.getCompareData>[0],
        )
        .then((data) => {
          if (cancelled) return;
          setByYear(applyTitle(applyByYearAliases(data)));
          setSingle(null);
          setFacet(null);
          setLineTotal(null);
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          setError(err instanceof Error ? err.message : "Error cargando gráfica.");
        })
        .finally(() => !cancelled && setLoading(false));
    } else if (template.compare_mode === "line-total") {
      const params: Record<string, string> = {
        job_ids: jobIds.join(","),
        tipo: template.tipo,
        un: template.un,
      };
      if (template.sub_filtro) params.sub_filtro = template.sub_filtro;
      if (template.loc) params.loc = template.loc;
      simulationApi
        .getCompareLineData(
          params as Parameters<typeof simulationApi.getCompareLineData>[0],
        )
        .then((data) => {
          if (cancelled) return;
          setLineTotal(applyTitle(applySeriesAliases(data)));
          setSingle(null);
          setFacet(null);
          setByYear(null);
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          setError(err instanceof Error ? err.message : "Error cargando gráfica.");
        })
        .finally(() => !cancelled && setLoading(false));
    } else {
      const params: Record<string, string> = {
        tipo: template.tipo,
        un: template.un,
      };
      if (template.sub_filtro) params.sub_filtro = template.sub_filtro;
      if (template.loc) params.loc = template.loc;
      if (template.variable) params.variable = template.variable;
      if (template.agrupar_por) params.agrupar_por = template.agrupar_por;
      const jobId = jobIds[0]!;
      simulationApi
        .getChartData(
          jobId,
          params as Parameters<typeof simulationApi.getChartData>[1],
        )
        .then((data) => {
          if (cancelled) return;
          setSingle(applyTitle(data));
          setFacet(null);
          setByYear(null);
          setLineTotal(null);
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          setError(err instanceof Error ? err.message : "Error cargando gráfica.");
        })
        .finally(() => !cancelled && setLoading(false));
    }

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    fingerprint,
    scenarioAliasSuffix,
    template.report_title,
    scenarioNames?.join("|"),
  ]);

  const selection = useMemo(() => templateToSelection(template), [template]);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 space-y-3 min-h-[360px] relative">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="m-0 text-sm font-semibold text-white break-words">
            {template.report_title || template.name}
          </h3>
          {template.report_title ? (
            <p className="m-0 text-[11px] text-slate-500 break-words">
              <span className="text-slate-600">Gráfica oficial:</span>{" "}
              {template.name}
            </p>
          ) : null}
          <p className="m-0 text-[11px] text-slate-500">
            {template.tipo} · {template.un}
            {template.compare_mode === "facet"
              ? ` · facet × ${template.num_scenarios}`
              : template.compare_mode === "by-year"
              ? ` · por año × ${template.num_scenarios}`
              : template.compare_mode === "line-total"
              ? ` · líneas totales × ${template.num_scenarios}`
              : ""}
          </p>
        </div>
      </div>

      <div className="rounded-lg border border-slate-800/70 bg-slate-950/30 p-3 min-h-[280px] relative">
        {loading ? (
          <div className="absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-slate-950/70 backdrop-blur-sm">
            <div className="flex flex-col items-center gap-2">
              <div className="h-6 w-6 rounded-full border-2 border-slate-700 border-t-emerald-500 animate-spin" />
              <span className="text-xs text-slate-400">Cargando…</span>
            </div>
          </div>
        ) : null}

        {error ? (
          <div className="rounded-md border border-rose-500/30 bg-rose-500/10 p-2 text-xs text-rose-200">
            {error}
          </div>
        ) : !ready ? (
          <div className="flex h-[260px] items-center justify-center text-xs text-slate-500 text-center px-4">
            Selecciona{" "}
            {template.num_scenarios === 1
              ? "un escenario"
              : `${template.num_scenarios} escenarios`}{" "}
            arriba para ver esta gráfica.
          </div>
        ) : template.compare_mode === "facet" && facet ? (
          <CompareChartFacet
            data={facet}
            barOrientation={
              (template.bar_orientation ?? "vertical") as "vertical" | "horizontal"
            }
            facetPlacement={
              (template.facet_placement ?? "inline") as "inline" | "stacked"
            }
            legendMode={
              (template.facet_legend_mode ?? "shared") as "shared" | "perFacet"
            }
            viewMode={template.view_mode === "line" ? "line" : "column"}
            serverFacetExport={{ jobIds, selection }}
            compactToolbar={compactToolbar}
          />
        ) : template.compare_mode === "by-year" && byYear ? (
          <CompareChart
            data={byYear}
            barOrientation={
              (template.bar_orientation ?? "vertical") as "vertical" | "horizontal"
            }
          />
        ) : template.compare_mode === "line-total" && lineTotal ? (
          <LineChart
            data={lineTotal}
            syntheticSeries={
              template.synthetic_series
                ? template.synthetic_series.filter((s) => s.active !== false)
                : undefined
            }
          />
        ) : template.view_mode === "pareto" && pareto ? (
          <ParetoChart
            data={pareto}
            serverExport={{ jobId: jobIds[0]!, selection }}
          />
        ) : template.view_mode === "line" && single ? (
          <LineChart
            data={single}
            serverExport={{ jobId: jobIds[0]!, selection }}
            syntheticSeries={
              template.synthetic_series
                ? template.synthetic_series.filter((s) => s.active !== false)
                : undefined
            }
          />
        ) : single ? (
          <HighchartsChart
            data={single}
            barOrientation={
              (template.bar_orientation ?? "vertical") as "vertical" | "horizontal"
            }
            serverExport={{ jobId: jobIds[0]!, selection }}
            stackType={template.view_mode === "area" ? "area" : "column"}
          />
        ) : !loading ? (
          <div className="flex h-[260px] items-center justify-center text-xs text-slate-500">
            Sin datos.
          </div>
        ) : null}
      </div>
    </div>
  );
}
