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
import { CompareChartFacet } from "@/shared/charts/CompareChartFacet";
import type {
  ChartDataResponse,
  CompareChartFacetResponse,
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
};

export function DashboardChartCard({
  template,
  jobIds,
  compactToolbar = false,
}: Props) {
  const [single, setSingle] = useState<ChartDataResponse | null>(null);
  const [facet, setFacet] = useState<CompareChartFacetResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ready =
    jobIds.length === template.num_scenarios && jobIds.every((j) => j != null);

  // Fingerprint estable para evitar re-fetch redundante.
  const fingerprint = `${template.id}|${template.compare_mode}|${jobIds.join(",")}`;

  useEffect(() => {
    if (!ready) {
      setSingle(null);
      setFacet(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);

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
          setFacet(data);
          setSingle(null);
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
          setSingle(data);
          setFacet(null);
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
  }, [fingerprint]);

  const selection = useMemo(() => templateToSelection(template), [template]);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 space-y-3 min-h-[360px] relative">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="m-0 text-sm font-semibold text-white break-words">
            {template.name}
          </h3>
          <p className="m-0 text-[11px] text-slate-500">
            {template.tipo} · {template.un}
            {template.compare_mode === "facet"
              ? ` · facet × ${template.num_scenarios}`
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
            serverFacetExport={{ jobIds, selection }}
            compactToolbar={compactToolbar}
          />
        ) : single ? (
          <HighchartsChart
            data={single}
            barOrientation={
              (template.bar_orientation ?? "vertical") as "vertical" | "horizontal"
            }
            serverExport={{ jobId: jobIds[0]!, selection }}
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
