/**
 * Modal de previsualización de una plantilla guardada.
 *
 * Permite elegir el/los escenarios requeridos y renderiza la gráfica usando los
 * mismos componentes que la página de resultados (HighchartsChart / CompareChartFacet).
 */
import { useEffect, useMemo, useState } from "react";
import { Modal } from "@/shared/components/Modal";
import { Button } from "@/shared/components/Button";
import { simulationApi } from "@/features/simulation/api/simulationApi";
import { HighchartsChart } from "@/shared/charts/HighchartsChart";
import { CompareChartFacet } from "@/shared/charts/CompareChartFacet";
import type {
  ChartDataResponse,
  CompareChartFacetResponse,
  SavedChartTemplate,
  SimulationRun,
} from "@/types/domain";
import type { ChartSelection } from "@/shared/charts/ChartSelector";

type Props = {
  open: boolean;
  onClose: () => void;
  template: SavedChartTemplate | null;
  availableJobs: SimulationRun[];
  loadingJobs: boolean;
};

function partitionJobs(jobs: SimulationRun[]): {
  favorites: SimulationRun[];
  others: SimulationRun[];
} {
  const sorted = [...jobs].sort(
    (a, b) => new Date(b.queued_at).getTime() - new Date(a.queued_at).getTime(),
  );
  const favorites: SimulationRun[] = [];
  const others: SimulationRun[] = [];
  for (const j of sorted) {
    (j.is_favorite ? favorites : others).push(j);
  }
  return { favorites, others };
}

function jobOptionLabel(r: SimulationRun): string {
  const bits: string[] = [];
  if (r.is_favorite) bits.push("★");
  bits.push(
    r.display_name?.trim() ||
      r.scenario_name?.trim() ||
      r.input_name?.trim() ||
      `Job ${r.id}`,
  );
  const tagName = r.scenario_tag?.name?.trim();
  if (tagName) bits.push(`[${tagName}]`);
  bits.push(`(#${r.id})`);
  return bits.join(" ");
}

function templateToSelection(t: SavedChartTemplate): ChartSelection {
  const sel: ChartSelection = { tipo: t.tipo, un: t.un };
  if (t.sub_filtro) sel.sub_filtro = t.sub_filtro;
  if (t.loc) sel.loc = t.loc;
  if (t.variable) sel.variable = t.variable;
  if (t.agrupar_por) sel.agrupar_por = t.agrupar_por;
  if (t.view_mode) sel.viewMode = t.view_mode;
  return sel;
}

export function PreviewChartModal({
  open,
  onClose,
  template,
  availableJobs,
  loadingJobs,
}: Props) {
  const [jobIds, setJobIds] = useState<(number | null)[]>([]);
  const [single, setSingle] = useState<ChartDataResponse | null>(null);
  const [facet, setFacet] = useState<CompareChartFacetResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset slots cuando cambia la plantilla o se abre el modal.
  useEffect(() => {
    if (!open || !template) return;
    setJobIds(Array.from({ length: template.num_scenarios }, () => null));
    setSingle(null);
    setFacet(null);
    setError(null);
  }, [open, template]);

  const setJobAt = (idx: number, value: number | null) => {
    setJobIds((prev) => {
      const next = [...prev];
      next[idx] = value;
      return next;
    });
  };

  const allJobsChosen =
    jobIds.length > 0 && jobIds.every((j) => j != null);

  useEffect(() => {
    if (!open || !template || !allJobsChosen) return;
    const ids = jobIds.filter((j): j is number => j != null);
    setLoading(true);
    setError(null);

    if (template.compare_mode === "facet") {
      const params: Record<string, string> = {
        job_ids: ids.join(","),
        tipo: template.tipo,
        un: template.un,
      };
      if (template.sub_filtro) params.sub_filtro = template.sub_filtro;
      if (template.loc) params.loc = template.loc;
      if (template.variable) params.variable = template.variable;
      if (template.agrupar_por) params.agrupar_por = template.agrupar_por;
      simulationApi
        .getCompareFacetData(params as Parameters<typeof simulationApi.getCompareFacetData>[0])
        .then((data) => {
          setFacet(data);
          setSingle(null);
        })
        .catch((err: unknown) => {
          setError(err instanceof Error ? err.message : "Error cargando gráfica.");
        })
        .finally(() => setLoading(false));
    } else {
      const params: Record<string, string> = {
        tipo: template.tipo,
        un: template.un,
      };
      if (template.sub_filtro) params.sub_filtro = template.sub_filtro;
      if (template.loc) params.loc = template.loc;
      if (template.variable) params.variable = template.variable;
      if (template.agrupar_por) params.agrupar_por = template.agrupar_por;
      const jobId = ids[0]!;
      simulationApi
        .getChartData(
          jobId,
          params as Parameters<typeof simulationApi.getChartData>[1],
        )
        .then((data) => {
          setSingle(data);
          setFacet(null);
        })
        .catch((err: unknown) => {
          setError(err instanceof Error ? err.message : "Error cargando gráfica.");
        })
        .finally(() => setLoading(false));
    }
  }, [open, template, allJobsChosen, jobIds]);

  const selection = useMemo(
    () => (template ? templateToSelection(template) : null),
    [template],
  );

  if (!template) return null;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Previsualizar · ${template.name}`}
      wide
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cerrar
          </Button>
        </div>
      }
    >
      <div className="grid gap-5">
        <section className="grid gap-2">
          <p className="m-0 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Escenario{template.num_scenarios > 1 ? "s" : ""} ·{" "}
            {template.num_scenarios} requerido
            {template.num_scenarios > 1 ? "s" : ""}
          </p>
          <div
            className="grid gap-2"
            style={{
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            }}
          >
            {jobIds.map((jobId, idx) => (
              <label key={idx} className="grid gap-1">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Escenario {idx + 1}
                </span>
                {(() => {
                  const { favorites, others } = partitionJobs(availableJobs);
                  return (
                    <select
                      value={jobId ?? ""}
                      onChange={(e) =>
                        setJobAt(
                          idx,
                          e.target.value ? Number(e.target.value) : null,
                        )
                      }
                      disabled={loadingJobs}
                      className="rounded-lg border border-slate-700 bg-slate-950/50 px-3 py-2 text-sm text-slate-100"
                    >
                      <option value="">
                        {loadingJobs ? "Cargando…" : "— Selecciona —"}
                      </option>
                      {favorites.length > 0 ? (
                        <optgroup label="★ Favoritos">
                          {favorites.map((j) => (
                            <option key={j.id} value={j.id}>
                              {jobOptionLabel(j)}
                            </option>
                          ))}
                        </optgroup>
                      ) : null}
                      {others.length > 0 ? (
                        <optgroup label="Otros">
                          {others.map((j) => (
                            <option key={j.id} value={j.id}>
                              {jobOptionLabel(j)}
                            </option>
                          ))}
                        </optgroup>
                      ) : null}
                    </select>
                  );
                })()}
              </label>
            ))}
          </div>
        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 min-h-[320px] relative">
          {loading ? (
            <div className="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-slate-950/70 backdrop-blur-sm">
              <div className="flex flex-col items-center gap-3">
                <div className="h-8 w-8 rounded-full border-2 border-slate-700 border-t-emerald-500 animate-spin" />
                <span className="text-sm font-medium text-slate-400">
                  Renderizando gráfico…
                </span>
              </div>
            </div>
          ) : null}

          {error ? (
            <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">
              {error}
            </div>
          ) : !allJobsChosen ? (
            <div className="flex h-[300px] items-center justify-center text-sm text-slate-500">
              Selecciona {template.num_scenarios === 1 ? "un escenario" : `${template.num_scenarios} escenarios`}{" "}
              para previsualizar la gráfica.
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
              serverFacetExport={{
                jobIds: jobIds.filter((j): j is number => j != null),
                selection: selection!,
              }}
            />
          ) : single ? (
            <HighchartsChart
              data={single}
              barOrientation={
                (template.bar_orientation ?? "vertical") as "vertical" | "horizontal"
              }
              serverExport={{
                jobId: jobIds[0] as number,
                selection: selection!,
              }}
            />
          ) : (
            <div className="flex h-[300px] items-center justify-center text-sm text-slate-500">
              Sin datos para previsualizar.
            </div>
          )}
        </section>
      </div>
    </Modal>
  );
}
