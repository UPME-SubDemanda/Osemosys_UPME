/**
 * Página de reportes:
 *   - Tab "Mis gráficas guardadas" → CRUD sobre las plantillas guardadas por el usuario.
 *   - Tab "Generador de reportes" → permite seleccionar plantillas, asignar los
 *     escenarios requeridos por cada una (según num_scenarios) y descargar un ZIP
 *     con una imagen por plantilla (PNG o SVG).
 *
 * La generación de reportes se apoya en `/saved-chart-templates/report`, que
 * renderiza cada gráfica con los mismos helpers que usa la página de resultados.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/shared/components/Button";
import { downloadBlob } from "@/shared/utils/downloadBlob";
import { savedChartsApi } from "@/features/reports/api/savedChartsApi";
import { simulationApi } from "@/features/simulation/api/simulationApi";
import {
  getChartModule,
  getChartModules,
  type ChartModuleInfo,
} from "@/shared/charts/ChartSelector";
import { paths } from "@/routes/paths";
import { useCurrentUser } from "@/app/providers/useCurrentUser";
import { PreviewChartModal } from "@/features/reports/components/PreviewChartModal";
import { CategoriesPanel } from "@/features/reports/components/CategoriesPanel";
import type {
  ReportLayout,
  ReportTemplateItem,
  SavedChartTemplate,
  SavedReport,
  SimulationRun,
} from "@/types/domain";
import {
  computeAutoLayout,
  expandLayoutForExport,
  reconcileLayout,
} from "@/features/reports/layout";

type TabId = "saved" | "generator" | "reports";

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("es-CO", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

/** Chip interactivo Público / Privado (clic para alternar si eres dueño). */
function VisibilityChip({
  isPublic,
  canEdit,
  onToggle,
}: {
  isPublic: boolean;
  canEdit: boolean;
  onToggle?: () => void;
}) {
  const label = isPublic ? "Público" : "Privado";
  const base = "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider";
  const cls = isPublic
    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
    : "border-amber-500/30 bg-amber-500/10 text-amber-300";
  if (!canEdit) {
    return <span className={`${base} ${cls}`} title={`Visibilidad: ${label}`}>{label}</span>;
  }
  return (
    <button
      type="button"
      onClick={onToggle}
      className={`${base} ${cls} cursor-pointer hover:brightness-125`}
      title={isPublic ? "Cambiar a privado" : "Cambiar a público"}
    >
      {label}
    </button>
  );
}

/** Badge "Oficial" (admin-editable). */
function OfficialChip({
  isOfficial,
  canEdit,
  onToggle,
}: {
  isOfficial: boolean;
  canEdit: boolean;
  onToggle?: () => void;
}) {
  const cls =
    "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider border-yellow-500/40 bg-yellow-500/10 text-yellow-300";
  if (!isOfficial && !canEdit) return null;
  if (!isOfficial && canEdit) {
    return (
      <button
        type="button"
        onClick={onToggle}
        className="inline-flex items-center gap-1 rounded-full border border-slate-700 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400 hover:text-yellow-300 hover:border-yellow-500/40"
        title="Marcar como oficial (visible a todos)"
      >
        Marcar oficial
      </button>
    );
  }
  if (canEdit) {
    return (
      <button
        type="button"
        onClick={onToggle}
        className={`${cls} cursor-pointer`}
        title="Quitar estado oficial"
      >
        ★ Oficial
      </button>
    );
  }
  return <span className={cls} title="Reporte oficial">★ Oficial</span>;
}

/** Parte favoritos/resto y ordena cada mitad por fecha descendente. */
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

/** Dropdown nativo con optgroup de Favoritos arriba. */
function JobSelect({
  value,
  onChange,
  jobs,
  loading,
  disabled,
}: {
  value: number | null;
  onChange: (next: number | null) => void;
  jobs: SimulationRun[];
  loading: boolean;
  disabled?: boolean;
}) {
  const { favorites, others } = partitionJobs(jobs);
  return (
    <select
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
      disabled={disabled ?? loading}
      className="rounded-lg border border-slate-700 bg-slate-950/50 px-3 py-2 text-sm text-slate-100"
    >
      <option value="">{loading ? "Cargando…" : "— Selecciona —"}</option>
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
}
function templateSummary(t: SavedChartTemplate): string {
  const bits: string[] = [];
  bits.push(`Tipo: ${t.tipo}`);
  bits.push(`Unidad: ${t.un}`);
  if (t.variable) bits.push(`Variable: ${t.variable}`);
  if (t.sub_filtro) bits.push(`Sub-filtro: ${t.sub_filtro}`);
  if (t.loc) bits.push(`Loc: ${t.loc}`);
  if (t.agrupar_por) bits.push(`Agrupar: ${t.agrupar_por}`);
  if (t.view_mode) bits.push(`Trazo: ${t.view_mode}`);
  bits.push(
    t.compare_mode === "facet"
      ? `Modo: comparación · ${t.num_scenarios} escenarios`
      : `Modo: único · 1 escenario`,
  );
  return bits.join(" · ");
}

// ─── Página ────────────────────────────────────────────────────────────────

export function ReportsPage() {
  const { user } = useCurrentUser();
  const canManageOfficial = Boolean(user?.can_manage_catalogs);
  const [tab, setTab] = useState<TabId>("reports");
  const [templates, setTemplates] = useState<SavedChartTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [availableJobs, setAvailableJobs] = useState<SimulationRun[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(true);

  const [reports, setReports] = useState<SavedReport[]>([]);
  const [loadingReports, setLoadingReports] = useState(true);
  /** Cuando se activa, el generador pre-carga un reporte guardado. */
  const [loadReportRequest, setLoadReportRequest] = useState<SavedReport | null>(
    null,
  );

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await savedChartsApi.list();
      setTemplates(rows);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Error cargando gráficas guardadas.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshReports = useCallback(async () => {
    setLoadingReports(true);
    try {
      const rows = await savedChartsApi.listReports();
      setReports(rows);
    } catch (err) {
      console.error("Error cargando reportes guardados", err);
    } finally {
      setLoadingReports(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    refreshReports();
  }, [refreshReports]);

  const handleLoadReport = useCallback((r: SavedReport) => {
    setLoadReportRequest(r);
    setTab("generator");
  }, []);

  // Auto-cargar un reporte si la URL trae ?load=<id> (vínculo desde el dashboard).
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const idStr = params.get("load");
    if (!idStr) return;
    const id = Number(idStr);
    if (!id) return;
    savedChartsApi
      .getReport(id)
      .then((r) => handleLoadReport(r))
      .catch((err) => console.error("Auto-load report failed", err))
      .finally(() => {
        // Limpia el query string para que no re-dispare al refrescar.
        const url = new URL(window.location.href);
        url.searchParams.delete("load");
        window.history.replaceState({}, "", url.toString());
      });
  }, [handleLoadReport]);

  useEffect(() => {
    setLoadingJobs(true);
    simulationApi
      .listRuns({ scope: "global", status_filter: "SUCCEEDED", cantidad: 100 })
      .then((res) => {
        // Solo escenarios con resultados utilizables: SUCCEEDED y NO infactibles.
        setAvailableJobs(
          (res.data ?? []).filter((r) => !r.is_infeasible_result),
        );
      })
      .catch(console.error)
      .finally(() => setLoadingJobs(false));
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 p-6 space-y-6 font-sans">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold tracking-tight text-white">Reportes</h1>
        <p className="m-0 text-sm text-slate-500 max-w-3xl">
          Guarda gráficas desde la página de resultados y combínalas aquí en un reporte.
          Cada plantilla recuerda sus filtros, unidades, tipo de trazo y cuántos
          escenarios necesita cuando se genera el reporte.
        </p>
      </header>

      <div
        role="tablist"
        aria-label="Secciones de reportes"
        className="inline-flex gap-1 rounded-xl border border-slate-800 bg-slate-900/60 p-1"
      >
        {[
          { id: "reports" as TabId, label: `Mis reportes guardados (${reports.length})` },
          { id: "generator" as TabId, label: "Generador de reporte" },
          { id: "saved" as TabId, label: `Mis gráficas guardadas (${templates.length})` },
        ].map((t) => {
          const active = t.id === tab;
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setTab(t.id)}
              className={`rounded-lg px-4 py-2 text-sm font-semibold transition-colors ${
                active
                  ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/25"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {error ? (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
          {error}
        </div>
      ) : null}

      {tab === "saved" ? (
        <SavedChartsTab
          templates={templates}
          loading={loading}
          onRefresh={refresh}
          availableJobs={availableJobs}
          loadingJobs={loadingJobs}
        />
      ) : tab === "reports" ? (
        <SavedReportsTab
          reports={reports}
          loading={loadingReports}
          onRefresh={refreshReports}
          onLoadReport={handleLoadReport}
          templates={templates}
          canManageOfficial={canManageOfficial}
        />
      ) : (
        <ReportGeneratorTab
          templates={templates}
          loading={loading}
          availableJobs={availableJobs}
          loadingJobs={loadingJobs}
          loadReportRequest={loadReportRequest}
          onLoadReportConsumed={() => setLoadReportRequest(null)}
          onReportSaved={refreshReports}
          savedReports={reports}
        />
      )}
    </div>
  );
}

// ─── Tab 1: Lista CRUD ──────────────────────────────────────────────────────

function SavedChartsTab({
  templates,
  loading,
  onRefresh,
  availableJobs,
  loadingJobs,
}: {
  templates: SavedChartTemplate[];
  loading: boolean;
  onRefresh: () => void;
  availableJobs: SimulationRun[];
  loadingJobs: boolean;
}) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [previewTemplate, setPreviewTemplate] =
    useState<SavedChartTemplate | null>(null);

  const startEdit = (tpl: SavedChartTemplate) => {
    setEditingId(tpl.id);
    setEditName(tpl.name);
    setEditDescription(tpl.description ?? "");
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditName("");
    setEditDescription("");
  };

  const saveEdit = async () => {
    if (editingId == null) return;
    const trimmed = editName.trim();
    if (!trimmed) return;
    setSaving(true);
    try {
      await savedChartsApi.update(editingId, {
        name: trimmed,
        description: editDescription.trim() || null,
      });
      cancelEdit();
      onRefresh();
    } catch (err) {
      alert(
        err instanceof Error ? err.message : "No se pudo actualizar la plantilla.",
      );
    } finally {
      setSaving(false);
    }
  };

  const remove = async (tpl: SavedChartTemplate) => {
    if (!confirm(`¿Eliminar la gráfica "${tpl.name}"?`)) return;
    try {
      await savedChartsApi.remove(tpl.id);
      onRefresh();
    } catch (err) {
      alert(err instanceof Error ? err.message : "No se pudo eliminar.");
    }
  };

  const toggleVisibility = async (tpl: SavedChartTemplate) => {
    try {
      await savedChartsApi.update(tpl.id, { is_public: !(tpl.is_public ?? false) });
      onRefresh();
    } catch (err) {
      alert(
        err instanceof Error
          ? err.message
          : "No se pudo cambiar la visibilidad.",
      );
    }
  };

  // ID del último resultado con datos (más reciente queued_at) para enlace rápido
  // al generador de gráficas individual de Resultados. Debe declararse antes de
  // cualquier early return para no violar las reglas de hooks.
  const latestRunId = useMemo(() => {
    if (availableJobs.length === 0) return null;
    let best = availableJobs[0]!;
    for (const r of availableJobs) {
      if (new Date(r.queued_at).getTime() > new Date(best.queued_at).getTime()) {
        best = r;
      }
    }
    return best.id;
  }, [availableJobs]);

  if (loading) {
    return (
      <div className="animate-pulse rounded-xl border border-slate-800 bg-slate-900/40 h-40" />
    );
  }

  const generateChartsButton = (
    <Link
      to={
        latestRunId != null ? paths.resultsDetail(latestRunId) : paths.results
      }
      className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold no-underline ${
        latestRunId != null
          ? "border-cyan-500/40 bg-cyan-500/10 text-cyan-300 hover:bg-cyan-500/20"
          : "border-slate-700 text-slate-500 cursor-not-allowed pointer-events-none"
      }`}
      title={
        latestRunId != null
          ? `Crea o guarda nuevas gráficas desde Resultados (último resultado #${latestRunId}).`
          : "No hay resultados disponibles todavía."
      }
      onClick={(e) => {
        if (latestRunId == null) e.preventDefault();
      }}
    >
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" />
      </svg>
      Generar gráficas →
    </Link>
  );

  if (templates.length === 0) {
    return (
      <>
      <div className="flex justify-end mb-3">{generateChartsButton}</div>
      <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-10 text-center">
        <h3 className="mb-2 text-lg font-semibold text-slate-200">
          Aún no tienes gráficas guardadas
        </h3>
        <p className="m-0 mx-auto max-w-md text-sm text-slate-500">
          Ve a{" "}
          <Link to={paths.results} className="text-cyan-400 hover:underline">
            Resultados
          </Link>
          , abre una simulación y usa el botón "Guardar gráfica" para crear tu
          primera plantilla.
        </p>
      </div>
      </>
    );
  }

  return (
    <>
    <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
      <p className="m-0 text-xs text-slate-500">
        {templates.length} gráfica{templates.length === 1 ? "" : "s"} accesible
        {templates.length === 1 ? "" : "s"} (propias + públicas + oficiales).
      </p>
      {generateChartsButton}
    </div>
    <div className="grid gap-3">
      {templates.map((tpl) => {
        const editing = editingId === tpl.id;
        return (
          <div
            key={tpl.id}
            className="rounded-xl border border-slate-800 bg-slate-900/40 p-5"
          >
            {editing ? (
              <div className="grid gap-3">
                <label className="grid gap-1">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    Nombre
                  </span>
                  <input
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="rounded-lg border border-slate-700 bg-slate-950/50 px-3 py-2 text-sm text-slate-100"
                  />
                </label>
                <label className="grid gap-1">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    Descripción
                  </span>
                  <textarea
                    value={editDescription}
                    onChange={(e) => setEditDescription(e.target.value)}
                    rows={4}
                    className="rounded-lg border border-slate-700 bg-slate-950/50 px-3 py-2 text-sm text-slate-100 resize-y font-mono"
                  />
                </label>
                <div className="flex gap-2 justify-end">
                  <Button variant="ghost" onClick={cancelEdit} disabled={saving}>
                    Cancelar
                  </Button>
                  <Button variant="primary" onClick={saveEdit} disabled={saving}>
                    {saving ? "Guardando…" : "Guardar cambios"}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0 flex-1 space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="m-0 text-base font-semibold text-white break-words">
                      {tpl.name}
                    </h3>
                    <VisibilityChip
                      isPublic={tpl.is_public ?? false}
                      canEdit={tpl.is_owner ?? true}
                      onToggle={() => toggleVisibility(tpl)}
                    />
                    {!tpl.is_owner ? (
                      <span className="rounded-full border border-slate-700 bg-slate-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                        de {tpl.owner_username ?? "otro"}
                      </span>
                    ) : null}
                  </div>
                  <p className="m-0 text-xs text-slate-500">
                    {templateSummary(tpl)}
                  </p>
                  {tpl.description ? (
                    <pre className="m-0 whitespace-pre-wrap break-words rounded-md border border-slate-800/70 bg-slate-950/40 p-3 text-[12px] text-slate-400 font-mono">
                      {tpl.description}
                    </pre>
                  ) : null}
                  <p className="m-0 text-[10px] text-slate-600">
                    Creada el {formatDate(tpl.created_at)} · ID {tpl.id}
                  </p>
                </div>
                <div className="flex gap-2 shrink-0 flex-wrap">
                  <button
                    type="button"
                    onClick={() => setPreviewTemplate(tpl)}
                    className="rounded-lg border border-cyan-500/40 px-3 py-1.5 text-xs font-medium text-cyan-300 hover:bg-cyan-500/10"
                    title="Previsualizar con un escenario"
                  >
                    Visualizar
                  </button>
                  {tpl.is_owner ? (
                    <>
                      <button
                        type="button"
                        onClick={() => startEdit(tpl)}
                        className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-800"
                      >
                        Editar
                      </button>
                      <button
                        type="button"
                        onClick={() => remove(tpl)}
                        className="rounded-lg border border-rose-500/40 px-3 py-1.5 text-xs font-medium text-rose-300 hover:bg-rose-500/10"
                      >
                        Eliminar
                      </button>
                    </>
                  ) : null}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
    <PreviewChartModal
      open={previewTemplate !== null}
      onClose={() => setPreviewTemplate(null)}
      template={previewTemplate}
      availableJobs={availableJobs}
      loadingJobs={loadingJobs}
    />
    </>
  );
}

// ─── Tab 2: Generador de reporte ────────────────────────────────────────────

/** Configuración de un ítem seleccionado (job_ids se resuelven en la generación). */
type SelectionData = {
  job_ids: (number | null)[];
};

const UNGROUPED_MODULE: ChartModuleInfo = {
  id: "_otros",
  label: "Otros",
  emoji: "📁",
};

function ReportGeneratorTab({
  templates,
  loading,
  availableJobs,
  loadingJobs,
  loadReportRequest,
  onLoadReportConsumed,
  onReportSaved,
  savedReports,
}: {
  templates: SavedChartTemplate[];
  loading: boolean;
  availableJobs: SimulationRun[];
  loadingJobs: boolean;
  loadReportRequest: SavedReport | null;
  onLoadReportConsumed: () => void;
  onReportSaved: () => void;
  savedReports: SavedReport[];
}) {
  /** Orden del reporte: lista ordenada de template_ids seleccionados. */
  const [order, setOrder] = useState<number[]>([]);
  /** Datos asociados (job_ids por template_id). */
  const [selectionData, setSelectionData] = useState<Record<number, SelectionData>>({});
  /** Qué acordeones están expandidos (por module id). */
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});
  /** Escenarios globales: slot i se propaga al slot i de cada plantilla. */
  const [globalScenarios, setGlobalScenarios] = useState<(number | null)[]>([]);

  const [fmt, setFmt] = useState<"png" | "svg">("png");
  const [organizeFolders, setOrganizeFolders] = useState(false);
  const [generating, setGenerating] = useState(false);

  /** Vista del paso 2: lista plana ordenada o agrupada por categorías. */
  const [viewMode, setViewMode] = useState<"list" | "categories">("list");
  /** Layout pendiente de guardar (override manual). null = aún no construido en este modo. */
  const [pendingLayout, setPendingLayout] = useState<ReportLayout | null>(null);
  const [generateError, setGenerateError] = useState<string | null>(null);

  /** Reporte que se está editando (loaded vs. nuevo). */
  const [currentReportId, setCurrentReportId] = useState<number | null>(null);
  /** Snapshot del reporte tal como vino del backend (para detectar cambios sin guardar). */
  const [loadedReport, setLoadedReport] = useState<SavedReport | null>(null);
  const [showSaveReportModal, setShowSaveReportModal] = useState(false);
  const [reportToast, setReportToast] = useState<string | null>(null);
  /** Modal "tienes cambios sin guardar" antes de ir al dashboard. */
  const [unsavedDashboardPrompt, setUnsavedDashboardPrompt] = useState(false);

  // ── Cargar un reporte guardado (desde la tab "Mis reportes") ──
  useEffect(() => {
    if (!loadReportRequest) return;
    const validIds = loadReportRequest.items.filter((id) =>
      templates.some((t) => t.id === id),
    );
    setOrder(validIds);
    setSelectionData(() => {
      const next: Record<number, SelectionData> = {};
      for (const tid of validIds) {
        const tpl = templates.find((t) => t.id === tid);
        if (tpl) {
          next[tid] = {
            job_ids: Array.from({ length: tpl.num_scenarios }, () => null),
          };
        }
      }
      return next;
    });
    setFmt(loadReportRequest.fmt);
    setCurrentReportId(loadReportRequest.id);
    setLoadedReport(loadReportRequest);
    // Si el reporte tiene layout persistido, abrir directamente en vista Categorías.
    if (loadReportRequest.layout) {
      setPendingLayout(loadReportRequest.layout);
      setViewMode("categories");
    } else {
      setPendingLayout(null);
      setViewMode("list");
    }
    onLoadReportConsumed();
  }, [loadReportRequest, templates, onLoadReportConsumed]);

  // Si estamos en vista Categorías, mantener pendingLayout sincronizado con el
  // orden: agregar nuevos ids a "Sin asignar", quitar los eliminados.
  const templatesByIdLocal = useMemo(
    () => new Map(templates.map((t) => [t.id, t])),
    [templates],
  );
  useEffect(() => {
    if (viewMode !== "categories" || !pendingLayout) return;
    setPendingLayout((prev) =>
      prev ? reconcileLayout(prev, order, templatesByIdLocal) : prev,
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [order, viewMode]);

  // Sincroniza selectionData con la lista de items: cualquier id que aparezca
  // en `order` debe tener un slot inicial para sus job_ids; los que ya no
  // están se quedan tal cual (no estorban).
  useEffect(() => {
    setSelectionData((prev) => {
      let changed = false;
      const next: Record<number, SelectionData> = { ...prev };
      for (const id of order) {
        if (next[id]) continue;
        const tpl = templatesByIdLocal.get(id);
        if (!tpl) continue;
        next[id] = {
          job_ids: Array.from({ length: tpl.num_scenarios }, () => null),
        };
        changed = true;
      }
      return changed ? next : prev;
    });
  }, [order, templatesByIdLocal]);

  // ── Agrupar plantillas por módulo (primer nivel de jerarquía) ──
  const groupedTemplates = useMemo(() => {
    const allModules = getChartModules();
    const byModule = new Map<string, SavedChartTemplate[]>();
    const moduleMeta = new Map<string, ChartModuleInfo>();
    for (const m of allModules) moduleMeta.set(m.id, m);
    for (const tpl of templates) {
      const mod = getChartModule(tpl.tipo) ?? UNGROUPED_MODULE;
      if (!moduleMeta.has(mod.id)) moduleMeta.set(mod.id, mod);
      const list = byModule.get(mod.id) ?? [];
      list.push(tpl);
      byModule.set(mod.id, list);
    }
    // Respetar el orden de allModules; al final, módulos no conocidos.
    const result: { module: ChartModuleInfo; templates: SavedChartTemplate[] }[] = [];
    const knownIds = new Set(allModules.map((m) => m.id));
    for (const m of allModules) {
      const items = byModule.get(m.id);
      if (items && items.length > 0) result.push({ module: m, templates: items });
    }
    for (const [id, items] of byModule.entries()) {
      if (knownIds.has(id)) continue;
      const meta = moduleMeta.get(id) ?? UNGROUPED_MODULE;
      result.push({ module: meta, templates: items });
    }
    return result;
  }, [templates]);

  // Expandir por defecto todos los grupos la primera vez que se cargan templates.
  useEffect(() => {
    setExpandedGroups((prev) => {
      if (Object.keys(prev).length > 0) return prev;
      const next: Record<string, boolean> = {};
      for (const { module } of groupedTemplates) next[module.id] = true;
      return next;
    });
  }, [groupedTemplates]);

  const selectedIds = useMemo(() => new Set(order), [order]);
  const orderIndexOf = (tplId: number) => order.indexOf(tplId);

  const addTemplate = (tpl: SavedChartTemplate) => {
    if (selectedIds.has(tpl.id)) return;
    setOrder((prev) => [...prev, tpl.id]);
    setSelectionData((prev) => ({
      ...prev,
      [tpl.id]: {
        job_ids: Array.from({ length: tpl.num_scenarios }, () => null),
      },
    }));
  };

  const removeTemplate = (tplId: number) => {
    setOrder((prev) => prev.filter((id) => id !== tplId));
    setSelectionData((prev) => {
      const next = { ...prev };
      delete next[tplId];
      return next;
    });
  };

  const toggleTemplate = (tpl: SavedChartTemplate) => {
    if (selectedIds.has(tpl.id)) removeTemplate(tpl.id);
    else addTemplate(tpl);
  };

  const setJobAt = (templateId: number, index: number, jobId: number | null) => {
    setSelectionData((prev) => {
      const item = prev[templateId];
      if (!item) return prev;
      const nextJobs = [...item.job_ids];
      nextJobs[index] = jobId;
      return { ...prev, [templateId]: { ...item, job_ids: nextJobs } };
    });
  };

  const moveUp = (tplId: number) => {
    setOrder((prev) => {
      const i = prev.indexOf(tplId);
      if (i <= 0) return prev;
      const next = [...prev];
      const tmp = next[i - 1]!;
      next[i - 1] = next[i]!;
      next[i] = tmp;
      return next;
    });
  };

  const moveDown = (tplId: number) => {
    setOrder((prev) => {
      const i = prev.indexOf(tplId);
      if (i < 0 || i >= prev.length - 1) return prev;
      const next = [...prev];
      const tmp = next[i + 1]!;
      next[i + 1] = next[i]!;
      next[i] = tmp;
      return next;
    });
  };

  // ── Select all / clear all ──
  const selectAll = () => {
    setOrder((prev) => {
      const existing = new Set(prev);
      const next = [...prev];
      for (const tpl of templates) {
        if (!existing.has(tpl.id)) next.push(tpl.id);
      }
      return next;
    });
    setSelectionData((prev) => {
      const next = { ...prev };
      for (const tpl of templates) {
        if (!next[tpl.id]) {
          next[tpl.id] = {
            job_ids: Array.from({ length: tpl.num_scenarios }, () => null),
          };
        }
      }
      return next;
    });
  };
  const clearAll = () => {
    setOrder([]);
    setSelectionData({});
  };
  const toggleGroupAll = (
    groupTemplates: SavedChartTemplate[],
    shouldSelect: boolean,
  ) => {
    if (shouldSelect) {
      setOrder((prev) => {
        const existing = new Set(prev);
        const next = [...prev];
        for (const tpl of groupTemplates) {
          if (!existing.has(tpl.id)) next.push(tpl.id);
        }
        return next;
      });
      setSelectionData((prev) => {
        const next = { ...prev };
        for (const tpl of groupTemplates) {
          if (!next[tpl.id]) {
            next[tpl.id] = {
              job_ids: Array.from({ length: tpl.num_scenarios }, () => null),
            };
          }
        }
        return next;
      });
    } else {
      const ids = new Set(groupTemplates.map((t) => t.id));
      setOrder((prev) => prev.filter((id) => !ids.has(id)));
      setSelectionData((prev) => {
        const next = { ...prev };
        for (const id of ids) delete next[id];
        return next;
      });
    }
  };

  // ── Lista ordenada materializada (para render del panel derecho y envío) ──
  const orderedItems = useMemo(() => {
    return order
      .map((id) => {
        const tpl = templates.find((t) => t.id === id);
        const data = selectionData[id];
        return tpl && data ? { tpl, data } : null;
      })
      .filter((x): x is { tpl: SavedChartTemplate; data: SelectionData } => x !== null);
  }, [order, templates, selectionData]);

  const allSelected =
    templates.length > 0 && orderedItems.length === templates.length;
  const someSelected = orderedItems.length > 0 && !allSelected;

  // ── Escenarios globales ──
  // N = máximo de num_scenarios entre las plantillas seleccionadas.
  const maxScenariosNeeded = useMemo(() => {
    let max = 0;
    for (const { tpl } of orderedItems) {
      if (tpl.num_scenarios > max) max = tpl.num_scenarios;
    }
    return max;
  }, [orderedItems]);

  // Redimensiona el vector de escenarios globales cuando cambia N.
  useEffect(() => {
    setGlobalScenarios((prev) => {
      if (prev.length === maxScenariosNeeded) return prev;
      const next: (number | null)[] = Array.from(
        { length: maxScenariosNeeded },
        (_, i) => prev[i] ?? null,
      );
      return next;
    });
  }, [maxScenariosNeeded]);

  const setGlobalScenarioAt = (idx: number, value: number | null) => {
    setGlobalScenarios((prev) => {
      const next = [...prev];
      next[idx] = value;
      return next;
    });
  };

  /** Propaga los escenarios globales a cada plantilla (hasta su num_scenarios). */
  const applyGlobalScenarios = () => {
    setSelectionData((prev) => {
      const next = { ...prev };
      for (const { tpl } of orderedItems) {
        const current = next[tpl.id];
        if (!current) continue;
        const nextJobs = [...current.job_ids];
        for (let i = 0; i < tpl.num_scenarios; i += 1) {
          const g = globalScenarios[i];
          if (g != null) nextJobs[i] = g;
        }
        next[tpl.id] = { ...current, job_ids: nextJobs };
      }
      return next;
    });
  };
  const clearAllAssignedJobs = () => {
    setSelectionData((prev) => {
      const next: Record<number, SelectionData> = {};
      for (const [id, data] of Object.entries(prev)) {
        next[Number(id)] = {
          job_ids: data.job_ids.map(() => null),
        };
      }
      return next;
    });
  };

  const canApplyGlobal =
    maxScenariosNeeded > 0 &&
    globalScenarios.slice(0, maxScenariosNeeded).some((j) => j != null);

  const canGenerate =
    orderedItems.length > 0 &&
    orderedItems.every(({ data }) => data.job_ids.every((j) => j != null));

  /** Compara el estado actual contra el reporte guardado en backend. */
  const isDirty = useMemo(() => {
    if (!loadedReport || !currentReportId) return false;
    const sameItems =
      JSON.stringify(loadedReport.items ?? []) === JSON.stringify(order);
    const sameLayout =
      JSON.stringify(loadedReport.layout ?? null) ===
      JSON.stringify(pendingLayout);
    const sameFmt = loadedReport.fmt === fmt;
    return !(sameItems && sameLayout && sameFmt);
  }, [loadedReport, currentReportId, order, pendingLayout, fmt]);

  /** Navega al dashboard del reporte actual, persistiendo escenarios. */
  const navigateToDashboard = () => {
    if (!currentReportId) return;
    const valid = globalScenarios.filter((j): j is number => j != null);
    if (valid.length > 0) {
      window.sessionStorage.setItem(
        `dashboard-prefill-scenarios:${currentReportId}`,
        JSON.stringify(valid),
      );
    }
    window.location.assign(paths.reportDashboard(currentReportId));
  };

  /** Guarda los cambios actuales del reporte cargado y luego ejecuta cb. */
  const saveCurrentReportAndThen = async (cb: () => void) => {
    if (!currentReportId) return;
    try {
      const updated = await savedChartsApi.updateReport(currentReportId, {
        items: order,
        fmt,
        layout: viewMode === "categories" ? pendingLayout : null,
      });
      setLoadedReport(updated);
      onReportSaved();
      cb();
    } catch (err) {
      alert(
        err instanceof Error ? err.message : "No se pudo guardar el reporte.",
      );
    }
  };

  const handleGenerate = async () => {
    if (!canGenerate) return;
    setGenerating(true);
    setGenerateError(null);
    try {
      const items: ReportTemplateItem[] = orderedItems.map(({ tpl, data }) => ({
        template_id: tpl.id,
        job_ids: data.job_ids.filter((j): j is number => j != null),
      }));
      // Si el usuario eligió "Organizar en carpetas", usamos el layout actual
      // (vista Categorías) o derivamos uno automático desde el orden plano.
      let categoriesPayload:
        | Awaited<ReturnType<typeof expandLayoutForExport>>
        | undefined;
      if (organizeFolders) {
        const layoutForExport =
          viewMode === "categories" && pendingLayout
            ? pendingLayout
            : computeAutoLayout(order, templatesByIdLocal);
        categoriesPayload = expandLayoutForExport(
          layoutForExport,
          templatesByIdLocal,
          orderedItems[0]?.data.job_ids.filter(
            (j): j is number => j != null,
          ) ?? [],
        );
        // expandLayoutForExport solo necesita los escenarios globales para
        // resolver job_ids; en el Generador, cada plantilla puede tener sus
        // propios escenarios, así que lo reemplazamos por el mapa real.
        const jobsByTemplate = new Map<number, number[]>(
          orderedItems.map(({ tpl, data }) => [
            tpl.id,
            data.job_ids.filter((j): j is number => j != null),
          ]),
        );
        const reassign = (
          arr: { template_id: number; job_ids: number[] }[],
        ) =>
          arr.map((x) => ({
            template_id: x.template_id,
            job_ids: jobsByTemplate.get(x.template_id) ?? x.job_ids,
          }));
        categoriesPayload = categoriesPayload.map((c) => ({
          ...c,
          items: reassign(c.items),
          subcategories: c.subcategories.map((s) => ({
            ...s,
            items: reassign(s.items),
          })),
        }));
      }
      const { blob, filename } = await savedChartsApi.generateReport({
        items,
        fmt,
        ...(organizeFolders && categoriesPayload
          ? { organize_by_category: true, categories: categoriesPayload }
          : {}),
      });
      downloadBlob(blob, filename);
    } catch (err: unknown) {
      let msg = "No se pudo generar el reporte.";
      if (err && typeof err === "object" && "message" in err) {
        msg = (err as { message?: string }).message ?? msg;
      }
      if (err && typeof err === "object" && "details" in err) {
        const resp = (err as { details?: { response?: unknown } }).details?.response;
        if (resp instanceof Blob && resp.type.includes("json")) {
          try {
            const text = await resp.text();
            const parsed = JSON.parse(text);
            if (typeof parsed.detail === "string") msg = parsed.detail;
          } catch {
            /* ignore */
          }
        }
      }
      setGenerateError(msg);
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="animate-pulse rounded-xl border border-slate-800 bg-slate-900/40 h-40" />
    );
  }

  if (templates.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-10 text-center text-sm text-slate-400">
        No hay gráficas guardadas. Guarda al menos una desde la página de resultados
        para poder generar un reporte.
      </div>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_420px]">
      {/* ── Columna izquierda: catálogo agrupado + selección ordenada ── */}
      <section className="space-y-6 min-w-0">
        <div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="m-0 text-sm font-semibold uppercase tracking-wider text-slate-500">
              1. Selecciona las gráficas a incluir
            </h2>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={selectAll}
                disabled={allSelected}
                className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-800 disabled:opacity-40"
              >
                Seleccionar todas
              </button>
              <button
                type="button"
                onClick={clearAll}
                disabled={orderedItems.length === 0}
                className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-400 hover:bg-slate-800 disabled:opacity-40"
              >
                Limpiar
              </button>
            </div>
          </div>
          <p className="mt-2 mb-0 text-xs text-slate-500">
            {allSelected
              ? `Todas las gráficas (${templates.length}) están seleccionadas.`
              : someSelected
                ? `${orderedItems.length} de ${templates.length} seleccionadas.`
                : `${templates.length} gráficas disponibles en ${groupedTemplates.length} grupos.`}
          </p>
        </div>

        <div className="space-y-3">
          {groupedTemplates.map(({ module, templates: groupTpls }) => {
            const groupSelectedCount = groupTpls.filter((t) =>
              selectedIds.has(t.id),
            ).length;
            const allInGroup = groupSelectedCount === groupTpls.length;
            const someInGroup = groupSelectedCount > 0 && !allInGroup;
            const expanded = expandedGroups[module.id] ?? true;
            return (
              <div
                key={module.id}
                className="rounded-xl border border-slate-800 bg-slate-900/30"
              >
                <header className="flex items-center gap-3 border-b border-slate-800/60 px-4 py-3">
                  <input
                    type="checkbox"
                    aria-label={`Seleccionar todas de ${module.label}`}
                    checked={allInGroup}
                    ref={(el) => {
                      if (el) el.indeterminate = someInGroup;
                    }}
                    onChange={(e) => toggleGroupAll(groupTpls, e.target.checked)}
                    className="h-4 w-4 shrink-0 cursor-pointer rounded border-slate-600 bg-slate-950 text-cyan-500 focus:ring-cyan-500/40"
                  />
                  <button
                    type="button"
                    onClick={() =>
                      setExpandedGroups((prev) => ({
                        ...prev,
                        [module.id]: !expanded,
                      }))
                    }
                    className="flex min-w-0 flex-1 items-center gap-2 text-left"
                  >
                    <span className="text-base">{module.emoji}</span>
                    <span className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-100">
                      {module.label}
                    </span>
                    <span className="shrink-0 rounded-full bg-slate-800/80 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      {groupSelectedCount}/{groupTpls.length}
                    </span>
                    <span
                      className={`shrink-0 text-slate-500 transition-transform ${
                        expanded ? "rotate-180" : ""
                      }`}
                      aria-hidden
                    >
                      ▾
                    </span>
                  </button>
                </header>
                {expanded ? (
                  <div className="grid gap-2 p-3">
                    {groupTpls.map((tpl) => {
                      const checked = selectedIds.has(tpl.id);
                      const orderIdx = orderIndexOf(tpl.id);
                      return (
                        <label
                          key={tpl.id}
                          className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
                            checked
                              ? "border-cyan-500/40 bg-cyan-500/5"
                              : "border-slate-800 bg-slate-900/30 hover:bg-slate-900/50"
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleTemplate(tpl)}
                            className="mt-1 h-4 w-4 shrink-0 cursor-pointer rounded border-slate-600 bg-slate-950 text-cyan-500 focus:ring-cyan-500/40"
                          />
                          <div className="min-w-0 flex-1 space-y-1">
                            <div className="flex items-center gap-2">
                              {checked ? (
                                <span className="shrink-0 rounded-full bg-cyan-500/20 px-2 py-0.5 text-[10px] font-bold tabular-nums text-cyan-300">
                                  #{orderIdx + 1}
                                </span>
                              ) : null}
                              <p className="m-0 text-sm font-semibold text-white break-words">
                                {tpl.name}
                              </p>
                            </div>
                            <p className="m-0 text-xs text-slate-500">
                              {templateSummary(tpl)}
                            </p>
                          </div>
                          <span className="shrink-0 rounded-full border border-slate-700 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                            {tpl.num_scenarios} esc.
                          </span>
                        </label>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>

        {/* ── 2. Orden + asignación de escenarios ── */}
        {orderedItems.length > 0 ? (
          <section className="space-y-3">
            <div>
              <h2 className="m-0 text-sm font-semibold uppercase tracking-wider text-slate-500">
                2. Ordena y asigna escenarios
              </h2>
              <p className="m-0 mt-1 text-xs text-slate-500">
                Reorganiza las gráficas con las flechas: el número de orden se
                incluye como prefijo en el nombre del archivo (ej.{" "}
                <code className="text-slate-400">01_Capacidad_…</code>,{" "}
                <code className="text-slate-400">02_Emisiones_…</code>).
              </p>
            </div>

            {/* ── Asignación global ── */}
            <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/5 p-4 space-y-3">
              <div className="flex flex-col gap-1">
                <p className="m-0 text-sm font-semibold text-emerald-200">
                  Escenarios globales del reporte
                </p>
                <p className="m-0 text-xs text-emerald-200/70">
                  Selecciona una vez los {maxScenariosNeeded}{" "}
                  escenario{maxScenariosNeeded === 1 ? "" : "s"} que usarán todas
                  las gráficas. Al aplicar, cada plantilla consume los primeros{" "}
                  <em>N</em> según sus necesidades (las comparativas usan todos;
                  las de un solo escenario usan solo el Escenario 1).
                </p>
              </div>

              <div
                className="grid gap-2"
                style={{
                  gridTemplateColumns:
                    "repeat(auto-fit, minmax(220px, 1fr))",
                }}
              >
                {Array.from({ length: maxScenariosNeeded }).map((_, idx) => {
                  const value = globalScenarios[idx] ?? null;
                  return (
                    <label key={idx} className="grid gap-1">
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-emerald-300/80">
                        Escenario {idx + 1}
                      </span>
                      <JobSelect
                        value={value}
                        onChange={(next) => setGlobalScenarioAt(idx, next)}
                        jobs={availableJobs}
                        loading={loadingJobs}
                      />
                    </label>
                  );
                })}
              </div>

              <div className="flex flex-wrap justify-end gap-2">
                <button
                  type="button"
                  onClick={clearAllAssignedJobs}
                  className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:bg-slate-800"
                >
                  Limpiar asignaciones
                </button>
                <button
                  type="button"
                  onClick={applyGlobalScenarios}
                  disabled={!canApplyGlobal}
                  className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Aplicar a todas las gráficas
                </button>
              </div>
            </div>

            {/* Toggle Lista / Categorías */}
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div
                role="group"
                aria-label="Vista del paso 2"
                className="inline-flex rounded-lg border border-slate-700 bg-slate-900/60 p-0.5"
              >
                <button
                  type="button"
                  onClick={() => setViewMode("list")}
                  className={`rounded-md px-3 py-1.5 text-xs font-semibold ${
                    viewMode === "list"
                      ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/25"
                      : "text-slate-400"
                  }`}
                >
                  Lista
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode("categories")}
                  className={`rounded-md px-3 py-1.5 text-xs font-semibold ${
                    viewMode === "categories"
                      ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/25"
                      : "text-slate-400"
                  }`}
                >
                  Categorías
                </button>
              </div>
              {viewMode === "categories" && pendingLayout ? (
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      const fresh = computeAutoLayout(order, templatesByIdLocal);
                      if (
                        confirm(
                          "Reemplazar el layout actual con las categorías por defecto (por módulo)?",
                        )
                      )
                        setPendingLayout(fresh);
                    }}
                    className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:bg-slate-800"
                  >
                    Restablecer auto
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (
                        confirm(
                          "Quitar todas las categorías y reagrupar todo en 'Sin asignar'?",
                        )
                      ) {
                        setPendingLayout({
                          categories: [
                            {
                              id: "_unassigned",
                              label: "Sin asignar",
                              items: [...order],
                              subcategories: [],
                            },
                          ],
                        });
                      }
                    }}
                    className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-400 hover:bg-slate-800"
                  >
                    Vaciar categorías
                  </button>
                </div>
              ) : null}
            </div>

            {viewMode === "list" ? (
              <ol className="grid gap-2 list-none p-0 m-0">
                {orderedItems.map(({ tpl, data }, idx) => {
                  const isFirst = idx === 0;
                  const isLast = idx === orderedItems.length - 1;
                  return (
                    <li
                      key={tpl.id}
                      className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 space-y-3"
                    >
                      <div className="flex flex-wrap items-start gap-3">
                        <span className="inline-flex h-8 w-10 shrink-0 items-center justify-center rounded-md border border-cyan-500/30 bg-cyan-500/10 text-sm font-bold tabular-nums text-cyan-300">
                          {String(idx + 1).padStart(2, "0")}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="m-0 text-sm font-semibold text-white break-words">
                            {tpl.name}
                          </p>
                          <p className="m-0 text-xs text-slate-500">
                            {templateSummary(tpl)}
                          </p>
                        </div>
                        <div className="flex shrink-0 items-center gap-1">
                          <button
                            type="button"
                            onClick={() => moveUp(tpl.id)}
                            disabled={isFirst}
                            title="Subir"
                            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-700 text-slate-300 hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed"
                          >
                            ↑
                          </button>
                          <button
                            type="button"
                            onClick={() => moveDown(tpl.id)}
                            disabled={isLast}
                            title="Bajar"
                            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-700 text-slate-300 hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed"
                          >
                            ↓
                          </button>
                          <button
                            type="button"
                            onClick={() => removeTemplate(tpl.id)}
                            title="Quitar del reporte"
                            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-rose-500/40 text-rose-300 hover:bg-rose-500/10"
                          >
                            ×
                          </button>
                        </div>
                      </div>
                      <div
                        className="grid gap-2"
                        style={{
                          gridTemplateColumns:
                            "repeat(auto-fit, minmax(220px, 1fr))",
                        }}
                      >
                        {data.job_ids.map((jobId, sIdx) => (
                          <label key={sIdx} className="grid gap-1">
                            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                              Escenario {sIdx + 1}
                            </span>
                            <JobSelect
                              value={jobId}
                              onChange={(next) => setJobAt(tpl.id, sIdx, next)}
                              jobs={availableJobs}
                              loading={loadingJobs}
                            />
                          </label>
                        ))}
                      </div>
                    </li>
                  );
                })}
              </ol>
            ) : pendingLayout ? (
              <CategoriesPanel
                layout={pendingLayout}
                onLayoutChange={setPendingLayout}
                items={order}
                onItemsChange={setOrder}
                accessibleTemplates={templates}
              />
            ) : (
              <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-6 space-y-3">
                <p className="m-0 text-sm font-semibold text-slate-200">
                  ¿Cómo quieres organizar las categorías?
                </p>
                <p className="m-0 text-xs text-slate-500">
                  Elige una opción para empezar. Después podrás renombrar,
                  agregar subcategorías y mover gráficas entre categorías.
                </p>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      setPendingLayout(
                        computeAutoLayout(order, templatesByIdLocal),
                      )
                    }
                    className="rounded-lg bg-cyan-600 px-4 py-2 text-xs font-semibold text-white hover:bg-cyan-500"
                  >
                    Crear con categorías por defecto
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setPendingLayout({
                        categories: [
                          {
                            id: "_unassigned",
                            label: "Sin asignar",
                            items: [...order],
                            subcategories: [],
                          },
                        ],
                      })
                    }
                    className="rounded-lg border border-slate-700 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-800"
                  >
                    Empezar en blanco
                  </button>
                </div>
              </div>
            )}
          </section>
        ) : null}
      </section>

      {/* ── Columna derecha: resumen + generar ── */}
      <aside className="h-fit rounded-xl border border-slate-800 bg-slate-900/40 p-5 space-y-5 lg:sticky lg:top-6">
        <div>
          <h2 className="m-0 text-sm font-semibold uppercase tracking-wider text-slate-500">
            Resumen del reporte
          </h2>
          <p className="m-0 mt-1 text-xs text-slate-500">
            Gráficas en el reporte:{" "}
            <strong className="text-slate-200">{orderedItems.length}</strong>
          </p>
          <p className="m-0 mt-1 text-xs text-slate-500">
            Se exportarán numeradas{" "}
            <code className="text-slate-400">01_</code>,{" "}
            <code className="text-slate-400">02_</code>, … en el orden mostrado.
          </p>
        </div>

        <div>
          <p className="m-0 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Formato de imagen
          </p>
          <div className="mt-2 inline-flex rounded-lg border border-slate-800 bg-slate-950/40 p-0.5">
            {(["png", "svg"] as const).map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => setFmt(f)}
                className={`rounded-md px-3 py-2 text-xs font-semibold transition-colors ${
                  fmt === f
                    ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/25"
                    : "text-slate-500 hover:text-slate-300 border border-transparent"
                }`}
              >
                {f.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        <label className="flex items-start gap-2 text-xs text-slate-300">
          <input
            type="checkbox"
            checked={organizeFolders}
            onChange={(e) => setOrganizeFolders(e.target.checked)}
            className="mt-0.5"
          />
          <span>
            <strong>Organizar en carpetas por categoría</strong>
            <br />
            <span className="text-slate-500 text-[11px]">
              {viewMode === "categories" && pendingLayout
                ? "Usa el layout que estás editando."
                : "Si no estás en vista Categorías, se agrupa automáticamente por módulo."}
            </span>
          </span>
        </label>

        {generateError ? (
          <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
            {generateError}
          </div>
        ) : null}

        <button
          type="button"
          onClick={handleGenerate}
          disabled={!canGenerate || generating}
          className="w-full rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {generating ? "Generando reporte…" : "Descargar reporte (.zip)"}
        </button>
        {!canGenerate && orderedItems.length > 0 ? (
          <p className="m-0 text-[11px] text-slate-500">
            Asigna un escenario en cada slot antes de generar.
          </p>
        ) : null}

        {/* ── Guardar el reporte como plantilla reutilizable ── */}
        <div className="border-t border-slate-800 pt-4 space-y-2">
          <p className="m-0 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Guardar este reporte
          </p>
          <p className="m-0 text-[11px] text-slate-500 leading-relaxed">
            Guarda la selección y el orden actuales con un nombre. Podrás
            recargarla más tarde desde "Mis reportes guardados".
          </p>
          {currentReportId ? (
            <p className="m-0 text-[10px] text-emerald-300/80">
              Editando reporte guardado #{currentReportId}.
            </p>
          ) : null}
          <button
            type="button"
            disabled={orderedItems.length === 0}
            onClick={() => setShowSaveReportModal(true)}
            className="w-full rounded-lg border border-cyan-500/40 bg-cyan-500/10 px-3 py-2 text-xs font-semibold text-cyan-300 hover:bg-cyan-500/20 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {currentReportId ? "Guardar cambios / Guardar como…" : "Guardar reporte…"}
          </button>
        </div>

        {/* ── Abrir el dashboard del reporte (requiere reporte guardado) ── */}
        <div className="border-t border-slate-800 pt-4 space-y-2">
          <p className="m-0 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Visualizar dashboard
          </p>
          <p className="m-0 text-[11px] text-slate-500 leading-relaxed">
            Abre el reporte como dashboard interactivo agrupado por categorías.
            Los escenarios globales actuales se aplicarán automáticamente.
          </p>
          <button
            type="button"
            disabled={!currentReportId}
            onClick={() => {
              if (!currentReportId) return;
              if (isDirty) {
                setUnsavedDashboardPrompt(true);
                return;
              }
              navigateToDashboard();
            }}
            title={
              currentReportId
                ? "Abrir dashboard"
                : "Guarda el reporte primero para abrir su dashboard"
            }
            className="w-full rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs font-semibold text-emerald-300 hover:bg-emerald-500/20 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Ver dashboard del reporte
          </button>
          {!currentReportId ? (
            <p className="m-0 text-[10px] text-slate-500">
              Guarda el reporte para habilitar el dashboard.
            </p>
          ) : isDirty ? (
            <p className="m-0 text-[10px] text-amber-400/80">
              Hay cambios sin guardar.
            </p>
          ) : null}
        </div>
      </aside>

      <SaveReportModal
        open={showSaveReportModal}
        onClose={() => setShowSaveReportModal(false)}
        items={order}
        fmt={fmt}
        existingReportId={currentReportId}
        existingReports={savedReports}
        layout={viewMode === "categories" ? pendingLayout : null}
        onSaved={(saved) => {
          setCurrentReportId(saved.id);
          setLoadedReport(saved);
          onReportSaved();
          setShowSaveReportModal(false);
          setReportToast(`Reporte "${saved.name}" guardado.`);
          window.setTimeout(() => setReportToast(null), 3500);
        }}
      />

      {reportToast ? (
        <div
          className="fixed bottom-6 right-6 z-[300] rounded-xl border border-cyan-500/40 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-200 shadow-2xl backdrop-blur-md"
          role="status"
        >
          {reportToast}
        </div>
      ) : null}

      {unsavedDashboardPrompt ? (
        <UnsavedChangesPrompt
          onCancel={() => setUnsavedDashboardPrompt(false)}
          onSaveAndGo={async () => {
            setUnsavedDashboardPrompt(false);
            await saveCurrentReportAndThen(navigateToDashboard);
          }}
          onDiscardAndGo={() => {
            setUnsavedDashboardPrompt(false);
            navigateToDashboard();
          }}
        />
      ) : null}
    </div>
  );
}

// ─── Modal: cambios sin guardar antes de ir al dashboard ────────────────────

function UnsavedChangesPrompt({
  onCancel,
  onSaveAndGo,
  onDiscardAndGo,
}: {
  onCancel: () => void;
  onSaveAndGo: () => void;
  onDiscardAndGo: () => void;
}) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      onClick={onCancel}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.55)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 250,
        padding: 16,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "min(480px, 100%)",
          background: "rgba(11,18,32,0.98)",
          border: "1px solid rgba(255,255,255,0.1)",
          borderRadius: 14,
          padding: 20,
          display: "grid",
          gap: 12,
        }}
      >
        <h3 className="m-0 text-lg font-semibold text-white">
          Tienes cambios sin guardar
        </h3>
        <p className="m-0 text-sm text-slate-300">
          El reporte tiene modificaciones que aún no se han guardado en el
          servidor. ¿Cómo quieres continuar al dashboard?
        </p>
        <div className="flex flex-wrap justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-slate-700 px-3 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-800"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={onDiscardAndGo}
            className="rounded-lg border border-amber-500/40 px-3 py-2 text-xs font-semibold text-amber-300 hover:bg-amber-500/10"
          >
            Ir sin guardar
          </button>
          <button
            type="button"
            onClick={onSaveAndGo}
            className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-500"
          >
            Guardar y abrir dashboard
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Modal: guardar reporte ─────────────────────────────────────────────────

function SaveReportModal({
  open,
  onClose,
  items,
  fmt,
  existingReportId,
  existingReports,
  onSaved,
  layout,
}: {
  open: boolean;
  onClose: () => void;
  items: number[];
  fmt: "png" | "svg";
  existingReportId: number | null;
  existingReports: SavedReport[];
  onSaved: (saved: SavedReport) => void;
  /** Layout en construcción (vista Categorías). null = modo auto en el dashboard. */
  layout?: ReportLayout | null;
}) {
  const existing = existingReportId
    ? existingReports.find((r) => r.id === existingReportId) ?? null
    : null;
  const [mode, setMode] = useState<"update" | "new">(existing ? "update" : "new");
  const [name, setName] = useState(existing?.name ?? "");
  const [description, setDescription] = useState(existing?.description ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setMode(existing ? "update" : "new");
    setName(existing?.name ?? "");
    setDescription(existing?.description ?? "");
    setError(null);
  }, [open, existing]);

  const handleSave = async () => {
    const trimmed = name.trim();
    if (mode === "new" && !trimmed) {
      setError("Asigna un nombre al reporte.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (mode === "update" && existing) {
        const updated = await savedChartsApi.updateReport(existing.id, {
          name: trimmed || existing.name,
          description: description.trim() || null,
          fmt,
          items,
          layout: layout ?? null,
        });
        onSaved(updated);
      } else {
        const created = await savedChartsApi.createReport({
          name: trimmed,
          description: description.trim() || null,
          fmt,
          items,
          layout: layout ?? null,
        });
        onSaved(created);
      }
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "message" in err
          ? (err as { message?: string }).message ?? "Error guardando el reporte."
          : "Error guardando el reporte.";
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.55)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 200,
        padding: 16,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "min(560px, 100%)",
          maxHeight: "calc(100vh - 32px)",
          overflowY: "auto",
          background: "rgba(11,18,32,0.98)",
          border: "1px solid rgba(255,255,255,0.1)",
          borderRadius: 14,
          padding: 20,
          display: "grid",
          gap: 14,
        }}
      >
        <h3 className="m-0 text-lg font-semibold text-white">
          {mode === "update" ? "Actualizar reporte guardado" : "Guardar reporte"}
        </h3>

        {existing ? (
          <div
            role="group"
            aria-label="Modo de guardado"
            className="inline-flex rounded-lg border border-slate-700 bg-slate-900/60 p-0.5"
          >
            <button
              type="button"
              onClick={() => setMode("update")}
              className={`rounded-md px-3 py-1.5 text-xs font-semibold ${
                mode === "update"
                  ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/25"
                  : "text-slate-400"
              }`}
            >
              Actualizar "{existing.name}"
            </button>
            <button
              type="button"
              onClick={() => setMode("new")}
              className={`rounded-md px-3 py-1.5 text-xs font-semibold ${
                mode === "new"
                  ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/25"
                  : "text-slate-400"
              }`}
            >
              Guardar como nuevo
            </button>
          </div>
        ) : null}

        <label className="grid gap-1">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Nombre
          </span>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={255}
            className="rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100"
          />
        </label>

        <label className="grid gap-1">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Descripción
          </span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            className="rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 resize-y"
          />
        </label>

        <p className="m-0 text-[11px] text-slate-500">
          Se guardan {items.length} gráfica{items.length === 1 ? "" : "s"} en el
          orden actual, formato {fmt.toUpperCase()}. Los escenarios se eligen al
          generar el reporte (no se persisten).
        </p>

        {error ? (
          <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
            {error}
          </div>
        ) : null}

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancelar
          </Button>
          <Button variant="primary" onClick={handleSave} disabled={saving}>
            {saving ? "Guardando…" : "Guardar"}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Tab: Mis reportes guardados ────────────────────────────────────────────

function SavedReportsTab({
  reports,
  loading,
  onRefresh,
  onLoadReport,
  templates,
  canManageOfficial,
}: {
  reports: SavedReport[];
  loading: boolean;
  onRefresh: () => void;
  onLoadReport: (r: SavedReport) => void;
  templates: SavedChartTemplate[];
  canManageOfficial: boolean;
}) {
  const templatesById = useMemo(
    () => new Map(templates.map((t) => [t.id, t])),
    [templates],
  );

  const handleDelete = async (r: SavedReport) => {
    if (!confirm(`¿Eliminar el reporte "${r.name}"?`)) return;
    try {
      await savedChartsApi.deleteReport(r.id);
      onRefresh();
    } catch (err) {
      alert(err instanceof Error ? err.message : "No se pudo eliminar.");
    }
  };

  const toggleVisibility = async (r: SavedReport) => {
    try {
      await savedChartsApi.updateReport(r.id, { is_public: !(r.is_public ?? false) });
      onRefresh();
    } catch (err) {
      alert(err instanceof Error ? err.message : "No se pudo cambiar la visibilidad.");
    }
  };

  const toggleOfficial = async (r: SavedReport) => {
    try {
      await savedChartsApi.updateReport(r.id, { is_official: !(r.is_official ?? false) });
      onRefresh();
    } catch (err) {
      alert(err instanceof Error ? err.message : "No se pudo cambiar el estado oficial.");
    }
  };

  if (loading) {
    return (
      <div className="animate-pulse rounded-xl border border-slate-800 bg-slate-900/40 h-40" />
    );
  }

  if (reports.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-10 text-center">
        <h3 className="mb-2 text-lg font-semibold text-slate-200">
          Aún no tienes reportes guardados
        </h3>
        <p className="m-0 mx-auto max-w-md text-sm text-slate-500">
          Desde el <em>Generador de reporte</em>, selecciona y organiza las
          gráficas y luego usa "Guardar reporte" para almacenar la colección
          con un nombre.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-3">
      {reports.map((r) => {
        const missing = r.items.filter((id) => !templatesById.has(id));
        return (
          <div
            key={r.id}
            className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 space-y-3"
          >
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0 flex-1 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="m-0 text-base font-semibold text-white break-words">
                    {r.name}
                  </h3>
                  <VisibilityChip
                    isPublic={r.is_public ?? false}
                    canEdit={(r.is_owner ?? true) || canManageOfficial}
                    onToggle={() => toggleVisibility(r)}
                  />
                  <OfficialChip
                    isOfficial={r.is_official ?? false}
                    canEdit={canManageOfficial}
                    onToggle={() => toggleOfficial(r)}
                  />
                  {!r.is_owner ? (
                    <span className="rounded-full border border-slate-700 bg-slate-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                      de {r.owner_username ?? "otro"}
                    </span>
                  ) : null}
                </div>
                <p className="m-0 text-xs text-slate-500">
                  {r.items.length} gráfica{r.items.length === 1 ? "" : "s"} · formato{" "}
                  {r.fmt.toUpperCase()} · actualizado {formatDate(r.updated_at)}
                </p>
                {r.description ? (
                  <p className="m-0 whitespace-pre-wrap break-words text-sm text-slate-300">
                    {r.description}
                  </p>
                ) : null}
                {missing.length > 0 ? (
                  <p className="m-0 text-[11px] text-amber-300">
                    ⚠ {missing.length} gráfica
                    {missing.length === 1 ? "" : "s"} referenciada
                    {missing.length === 1 ? "" : "s"} ya no existe
                    {missing.length === 1 ? "" : "n"}; se omitirán al cargar.
                  </p>
                ) : null}
              </div>
              <div className="flex shrink-0 gap-2 flex-wrap">
                <Link
                  to={paths.reportDashboard(r.id)}
                  className="rounded-lg border border-cyan-500/40 bg-cyan-500/10 px-3 py-1.5 text-xs font-semibold text-cyan-300 hover:bg-cyan-500/20 no-underline"
                  title="Abrir dashboard interactivo"
                >
                  Ver dashboard
                </Link>
                <button
                  type="button"
                  onClick={() => onLoadReport(r)}
                  className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold text-emerald-300 hover:bg-emerald-500/20"
                  title="Cargar en el generador"
                >
                  Cargar → Generador
                </button>
                {(r.is_owner ?? true) || canManageOfficial ? (
                  <button
                    type="button"
                    onClick={() => handleDelete(r)}
                    className="rounded-lg border border-rose-500/40 px-3 py-1.5 text-xs font-medium text-rose-300 hover:bg-rose-500/10"
                  >
                    Eliminar
                  </button>
                ) : null}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
