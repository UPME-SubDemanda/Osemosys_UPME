/**
 * Dashboard de un reporte guardado:
 *   - Muestra las gráficas del reporte agrupadas en pestañas por categoría
 *     (módulo del MENU). Para "Demanda Final" hay sub-pestañas por sector.
 *   - Un panel arriba selecciona los N escenarios globales que consumen todas
 *     las gráficas (mismo patrón que el Generador).
 *   - Modo edición permite renombrar categorías, crear categorías custom,
 *     mover gráficas entre categorías, eliminar categorías custom y
 *     restaurar el layout automático.
 *   - Sidebar de export: ZIP plano u "Organizado en carpetas por categoría".
 */
import type { Dispatch, SetStateAction } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Button } from "@/shared/components/Button";
import { JobSelect } from "@/shared/components/JobSelect";
import { downloadBlob } from "@/shared/utils/downloadBlob";
import { savedChartsApi } from "@/features/reports/api/savedChartsApi";
import { simulationApi } from "@/features/simulation/api/simulationApi";
import { paths } from "@/routes/paths";
import { DashboardChartCard } from "@/features/reports/components/DashboardChartCard";
import { ChartPicker } from "@/features/reports/components/CategoriesPanel";
import { ChartPickerModal } from "@/features/reports/components/ChartPickerModal";
import { IconPencil, IconSwap } from "@/features/reports/components/CardActionIcons";
import { RowScenarioPicker } from "@/features/reports/components/RowScenarioPicker";
import { pickRepresentativeJob } from "@/features/reports/pickRepresentativeJob";
import {
  loadReportScenarios,
  saveReportScenarios,
} from "@/features/reports/scenarioMemory";
import { useCurrentUser } from "@/app/providers/useCurrentUser";
import {
  effectiveLayout,
  expandLayoutForExport,
  reconcileLayout,
} from "@/features/reports/layout";
import type {
  ReportLayout,
  SavedChartTemplate,
  SavedReport,
  SimulationRun,
} from "@/types/domain";

// ─── Helpers de selección de escenario ──────────────────────────────────────

// JobSelect enriquecido se importa desde shared/components.

// ─── Página principal ───────────────────────────────────────────────────────

export function ReportDashboardPage() {
  const { reportId } = useParams<{ reportId: string }>();
  const navigate = useNavigate();
  const numericReportId = Number(reportId);
  const { user: currentUser } = useCurrentUser();

  const [report, setReport] = useState<SavedReport | null>(null);
  const [templates, setTemplates] = useState<SavedChartTemplate[]>([]);
  const [availableJobs, setAvailableJobs] = useState<SimulationRun[]>([]);
  const [loadingReport, setLoadingReport] = useState(true);
  const [loadingTemplates, setLoadingTemplates] = useState(true);
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [globalScenarios, setGlobalScenarios] = useState<(number | null)[]>([]);
  /** Alias por escenario global (persistido en el reporte). */
  const [scenarioAliases, setScenarioAliases] = useState<string[]>([]);
  /** Copia de aliases en modo edición para poder descartar cambios. */
  const [draftAliases, setDraftAliases] = useState<string[] | null>(null);
  const [activeCategoryId, setActiveCategoryId] = useState<string | null>(null);
  const [activeSubcatId, setActiveSubcatId] = useState<string | null>(null);

  // Modo edición
  const [editing, setEditing] = useState(false);
  const [draftLayout, setDraftLayout] = useState<ReportLayout | null>(null);
  /** Lista de items en edición; permite agregar/quitar gráficas. */
  const [draftItems, setDraftItems] = useState<number[] | null>(null);
  /**
   * Overrides de escenarios por template (solo modo edición).
   * Key: templateId → índices 0-based en globalScenarios que usa esa plantilla.
   * Null/ausente = default (primeros num_scenarios slots).
   */
  const [slotOverrides, setSlotOverrides] = useState<Record<number, number[]>>({});
  const [savingLayout, setSavingLayout] = useState(false);

  // Exportación (popover en header)
  const [organizeFolders, setOrganizeFolders] = useState(true);
  const [fmt, setFmt] = useState<"png" | "svg">("png");
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  /** Renombres por job_id solo para este export; no muta el display_name real. */
  const [renameOverrides, setRenameOverrides] = useState<Record<number, string>>({});
  const [renameOpen, setRenameOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  // Rango de años persistido en el reporte. ``null`` = sin tope por ese lado.
  const [yearFrom, setYearFrom] = useState<number | null>(null);
  const [yearTo, setYearTo] = useState<number | null>(null);
  const [savingYears, setSavingYears] = useState(false);

  // Ancho por gráfica (single-scenario): "half" = 50%, "full" = 100%.
  // Las facets siempre 100%.
  const [cardWidthById, setCardWidthById] = useState<Record<number, "half" | "full">>({});

  // ── Carga inicial ──
  const refreshReport = useCallback(async () => {
    if (!numericReportId) return;
    setLoadingReport(true);
    setError(null);
    try {
      const r = await savedChartsApi.getReport(numericReportId);
      setReport(r);
      setScenarioAliases(
        Array.isArray(r.scenario_aliases) ? [...r.scenario_aliases] : [],
      );
      setYearFrom(typeof r.year_from === "number" ? r.year_from : null);
      setYearTo(typeof r.year_to === "number" ? r.year_to : null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "No se pudo cargar el reporte.");
      setReport(null);
    } finally {
      setLoadingReport(false);
    }
  }, [numericReportId]);

  useEffect(() => {
    refreshReport();
  }, [refreshReport]);

  useEffect(() => {
    setLoadingTemplates(true);
    savedChartsApi
      .list()
      .then((rows) => setTemplates(rows))
      .catch(console.error)
      .finally(() => setLoadingTemplates(false));
  }, []);

  useEffect(() => {
    setLoadingJobs(true);
    simulationApi
      .listRuns({ scope: "global", status_filter: "SUCCEEDED", cantidad: 100 })
      .then((res) =>
        setAvailableJobs((res.data ?? []).filter((r) => !r.is_infeasible_result)),
      )
      .catch(console.error)
      .finally(() => setLoadingJobs(false));
  }, []);

  // ── Mapas y layout efectivo ──
  const templatesById = useMemo(
    () => new Map(templates.map((t) => [t.id, t])),
    [templates],
  );

  const baseLayout = useMemo<ReportLayout>(() => {
    if (!report) return { categories: [] };
    return reconcileLayout(
      effectiveLayout(report, templatesById),
      report.items ?? [],
      templatesById,
    );
  }, [report, templatesById]);

  const layout = editing && draftLayout ? draftLayout : baseLayout;

  // Tab inicial = primera categoría
  useEffect(() => {
    if (layout.categories.length === 0) {
      setActiveCategoryId(null);
      setActiveSubcatId(null);
      return;
    }
    if (
      activeCategoryId == null ||
      !layout.categories.some((c) => c.id === activeCategoryId)
    ) {
      setActiveCategoryId(layout.categories[0]!.id);
      setActiveSubcatId(null);
    }
  }, [layout, activeCategoryId]);

  const activeCategory = useMemo(
    () =>
      layout.categories.find((c) => c.id === activeCategoryId) ?? null,
    [layout, activeCategoryId],
  );
  /**
   * Id virtual para el tab "General": representa los items directos de una
   * categoría (los que no están en ninguna subcategoría). No se persiste en
   * el layout: es solo UI.
   */
  const GENERAL_SUBCAT_ID = "__general__";
  useEffect(() => {
    if (!activeCategory) return;
    const validSubIds = new Set(activeCategory.subcategories.map((s) => s.id));
    const hasDirectItems = activeCategory.items.length > 0;
    // Si la subcat actual ya no existe (o es null pero hay subcats):
    //   - preferir "General" si hay items directos,
    //   - si no, caer a la primera subcat,
    //   - si no hay nada, quedar en null.
    const current = activeSubcatId;
    const isValid =
      current === GENERAL_SUBCAT_ID
        ? hasDirectItems
        : current != null && validSubIds.has(current);
    if (!isValid) {
      if (hasDirectItems) {
        setActiveSubcatId(GENERAL_SUBCAT_ID);
      } else if (activeCategory.subcategories.length > 0) {
        setActiveSubcatId(activeCategory.subcategories[0]!.id);
      } else {
        setActiveSubcatId(null);
      }
    }
  }, [activeCategory, activeSubcatId]);

  // ── Escenarios globales ──
  const maxScenariosNeeded = useMemo(() => {
    if (!report) return 0;
    let max = 0;
    for (const id of report.items ?? []) {
      const tpl = templatesById.get(id);
      if (!tpl) continue;
      if (tpl.num_scenarios > max) max = tpl.num_scenarios;
      const override = slotOverrides[tpl.id];
      if (override && override.length > 0) {
        const rowMax = Math.max(...override) + 1;
        if (rowMax > max) max = rowMax;
      }
    }
    return max;
  }, [report, templatesById, slotOverrides]);

  // Prefill de escenarios al abrir el reporte. Prioridad:
  //   1) sessionStorage (explícito, ej. desde "Ver en reporte" de Resultados);
  //   2) default_job_ids del reporte (si existen, siempre aplican);
  //   3) memoria client-side (última sesión en este navegador).
  const [pendingPrefill, setPendingPrefill] = useState<(number | null)[] | null>(null);
  // 1) sessionStorage: se consume al montar.
  useEffect(() => {
    if (!numericReportId) return;
    const key = `dashboard-prefill-scenarios:${numericReportId}`;
    const raw = window.sessionStorage.getItem(key);
    if (!raw) return;
    try {
      const arr = JSON.parse(raw);
      if (Array.isArray(arr)) {
        setPendingPrefill(
          arr.map((v) => (typeof v === "number" ? v : null)),
        );
      }
    } catch {
      /* ignore */
    } finally {
      window.sessionStorage.removeItem(key);
    }
  }, [numericReportId]);

  // 2) default_job_ids — siempre ganan sobre la memoria client-side cuando
  //    no hay prefill explícito. Se aplica en cuanto `report` llega.
  // 3) fallback a localStorage si no hay defaults.
  useEffect(() => {
    if (!report) return;
    if (pendingPrefill != null) return;
    if (globalScenarios.some((v) => v != null)) return;
    const savedDefaults = Array.isArray(report.default_job_ids)
      ? report.default_job_ids
      : null;
    const hasDefaults = savedDefaults && savedDefaults.some((v) => v != null);
    if (hasDefaults) {
      setPendingPrefill([...(savedDefaults as (number | null)[])]);
      return;
    }
    const remembered = loadReportScenarios(numericReportId);
    if (remembered && remembered.length > 0) {
      setPendingPrefill(remembered);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report]);

  // Persiste los escenarios elegidos para este reporte.
  useEffect(() => {
    if (!numericReportId) return;
    saveReportScenarios(numericReportId, globalScenarios);
  }, [numericReportId, globalScenarios]);

  // Redimensiona globalScenarios cuando cambia maxScenariosNeeded; si hay
  // prefill pendiente, lo aplica una sola vez en cuanto sabemos cuántos
  // slots tenemos (>0) y luego lo descarta.
  useEffect(() => {
    if (maxScenariosNeeded === 0) return; // aún no sabemos; no toques nada.
    setGlobalScenarios((prev) => {
      if (
        !pendingPrefill &&
        prev.length === maxScenariosNeeded
      ) {
        return prev;
      }
      const source = pendingPrefill ?? prev;
      return Array.from(
        { length: maxScenariosNeeded },
        (_, i) => source[i] ?? prev[i] ?? null,
      );
    });
    if (pendingPrefill) {
      setPendingPrefill(null);
    }
  }, [maxScenariosNeeded, pendingPrefill]);

  const setGlobalScenarioAt = (idx: number, value: number | null) => {
    setGlobalScenarios((prev) => {
      const next = [...prev];
      next[idx] = value;
      return next;
    });
  };

  /**
   * Cuando una gráfica de 1 solo escenario vive en un reporte con múltiples,
   * devuelve el alias del escenario al que corresponde para agregarlo al
   * título. Para charts multi-escenario no se agrega nada.
   */
  const resolveAliasSuffix = useCallback(
    (tpl: SavedChartTemplate): string | undefined => {
      if (tpl.num_scenarios !== 1) return undefined;
      const totalSlots = Math.max(
        (scenarioAliases ?? []).length,
        globalScenarios.length,
      );
      if (totalSlots <= 1) return undefined;
      const override = slotOverrides[tpl.id];
      const slotIdx = override && override.length > 0 ? override[0] : 0;
      const alias = scenarioAliases[slotIdx as number]?.trim();
      return alias && alias.length > 0 ? alias : `Escenario ${(slotIdx as number) + 1}`;
    },
    [slotOverrides, scenarioAliases, globalScenarios],
  );

  /**
   * Para cada slot usado por el template, devuelve el alias (o "Escenario N").
   * Se aplica como override al nombre de series/facets en el render.
   */
  const resolveScenarioNames = useCallback(
    (tpl: SavedChartTemplate): string[] => {
      const override = slotOverrides[tpl.id];
      const slots =
        override && override.length > 0
          ? override.slice(0, tpl.num_scenarios)
          : Array.from({ length: tpl.num_scenarios }, (_, i) => i);
      return slots.map((s) => {
        const a = scenarioAliases[s]?.trim();
        return a && a.length > 0 ? a : `Escenario ${s + 1}`;
      });
    },
    [slotOverrides, scenarioAliases],
  );

  const jobIdsForTemplate = useCallback(
    (tpl: SavedChartTemplate): number[] => {
      const override = slotOverrides[tpl.id];
      const slots =
        override && override.length > 0
          ? override.slice(0, tpl.num_scenarios)
          : Array.from({ length: tpl.num_scenarios }, (_, i) => i);
      const out: number[] = [];
      for (const slotIdx of slots) {
        const j = globalScenarios[slotIdx];
        if (j == null) return [];
        out.push(j);
      }
      if (out.length < tpl.num_scenarios) return [];
      return out;
    },
    [globalScenarios, slotOverrides],
  );

  // ── Permisos / capacidad de edición ──
  const isAdminReports = Boolean(
    currentUser?.is_admin_reports ?? currentUser?.can_manage_scenarios,
  );
  const canEdit = Boolean(
    report?.is_owner
      || (isAdminReports && (report?.is_official ?? false))
  );
  /** Cualquier usuario con permiso de admin_reports puede reetiquetar títulos de charts. */
  const canEditChartReportTitle = (tpl: SavedChartTemplate): boolean =>
    Boolean(tpl.is_owner) || isAdminReports;

  // ── Handlers de edición de layout ──
  const startEditing = () => {
    setDraftLayout(JSON.parse(JSON.stringify(baseLayout)) as ReportLayout);
    setDraftItems([...(report?.items ?? [])]);
    setDraftAliases([...scenarioAliases]);
    setEditing(true);
  };
  const cancelEditing = () => {
    setEditing(false);
    setDraftLayout(null);
    setDraftItems(null);
    setDraftAliases(null);
  };

  // ── Mutaciones del draftLayout (modo edición) ──────────────────────────
  const mutateLayout = (fn: (l: ReportLayout) => ReportLayout) => {
    setDraftLayout((prev) => (prev ? fn(prev) : prev));
  };

  const setSubcatDisplayDraft = (mode: "tabs" | "accordions") =>
    mutateLayout((l) => ({ ...l, subcategory_display: mode }));

  const renameCategoryDraft = (id: string, label: string) =>
    mutateLayout((l) => ({
      ...l,
      categories: l.categories.map((c) =>
        c.id === id ? { ...c, label } : c,
      ),
    }));
  const renameSubDraft = (catId: string, subId: string, label: string) =>
    mutateLayout((l) => ({
      ...l,
      categories: l.categories.map((c) =>
        c.id === catId
          ? {
              ...c,
              subcategories: c.subcategories.map((s) =>
                s.id === subId ? { ...s, label } : s,
              ),
            }
          : c,
      ),
    }));
  const addCategoryDraft = () => {
    const id = `custom_${Date.now()}`;
    mutateLayout((l) => ({
      ...l,
      categories: [
        ...l.categories,
        { id, label: "Nueva categoría", items: [], subcategories: [] },
      ],
    }));
    setActiveCategoryId(id);
  };
  const addSubDraft = (catId: string) => {
    const id = `sub_${Date.now()}`;
    mutateLayout((l) => ({
      ...l,
      categories: l.categories.map((c) =>
        c.id === catId
          ? {
              ...c,
              subcategories: [
                ...c.subcategories,
                { id, label: "Nueva subcategoría", items: [] },
              ],
            }
          : c,
      ),
    }));
    setActiveSubcatId(id);
  };
  const removeCategoryDraft = (catId: string) => {
    mutateLayout((l) => {
      const cat = l.categories.find((c) => c.id === catId);
      if (!cat) return l;
      const orphaned = [
        ...cat.items,
        ...cat.subcategories.flatMap((s) => s.items),
      ];
      const remaining = l.categories.filter((c) => c.id !== catId);
      if (orphaned.length === 0) return { ...l, categories: remaining };
      const idx = remaining.findIndex((c) => c.id === "_unassigned");
      if (idx >= 0) {
        const u = remaining[idx]!;
        remaining[idx] = { ...u, items: [...u.items, ...orphaned] };
      } else {
        remaining.push({
          id: "_unassigned",
          label: "Sin asignar",
          items: orphaned,
          subcategories: [],
        });
      }
      return { ...l, categories: remaining };
    });
    if (activeCategoryId === catId) setActiveCategoryId(null);
  };
  /**
   * Navega a la página de resultados para crear una gráfica nueva y volver al
   * dashboard con ella ya agregada. Codifica en la URL: report, target cat/sub
   * y kind="dashboard".
   */
  const startCreateNewChart = (
    target: { catId: string; subId?: string } | null,
  ) => {
    if (!report) return;
    const job = pickRepresentativeJob(
      availableJobs,
      globalScenarios.filter((j): j is number => j != null),
    );
    if (!job) {
      alert(
        "No hay resultados disponibles para crear una gráfica. Lanza una simulación primero.",
      );
      return;
    }
    const params = new URLSearchParams();
    params.set("addToReport", String(report.id));
    params.set("addMode", "dashboard");
    if (target?.catId) params.set("addCatId", target.catId);
    if (target?.subId) params.set("addSubId", target.subId);
    navigate(`${paths.resultsDetail(job.id)}?${params.toString()}`);
  };

  const moveCategoryDraft = (id: string, delta: -1 | 1) => {
    mutateLayout((l) => {
      const idx = l.categories.findIndex((c) => c.id === id);
      if (idx < 0) return l;
      const target = idx + delta;
      if (target < 0 || target >= l.categories.length) return l;
      const next = [...l.categories];
      const tmp = next[idx]!;
      next[idx] = next[target]!;
      next[target] = tmp;
      return { ...l, categories: next };
    });
  };
  const moveSubDraft = (catId: string, subId: string, delta: -1 | 1) => {
    mutateLayout((l) => ({
      ...l,
      categories: l.categories.map((c) => {
        if (c.id !== catId) return c;
        const idx = c.subcategories.findIndex((s) => s.id === subId);
        if (idx < 0) return c;
        const target = idx + delta;
        if (target < 0 || target >= c.subcategories.length) return c;
        const next = [...c.subcategories];
        const tmp = next[idx]!;
        next[idx] = next[target]!;
        next[target] = tmp;
        return { ...c, subcategories: next };
      }),
    }));
  };

  const removeSubDraft = (catId: string, subId: string) => {
    mutateLayout((l) => ({
      ...l,
      categories: l.categories.map((c) => {
        if (c.id !== catId) return c;
        const sub = c.subcategories.find((s) => s.id === subId);
        return {
          ...c,
          items: [...c.items, ...(sub?.items ?? [])],
          subcategories: c.subcategories.filter((s) => s.id !== subId),
        };
      }),
    }));
    if (activeSubcatId === subId) setActiveSubcatId(null);
  };
  const moveItemDraft = (
    itemId: number,
    target: { catId: string; subId?: string },
  ) => {
    mutateLayout((l) => {
      const stripped = l.categories.map((c) => ({
        ...c,
        items: c.items.filter((id) => id !== itemId),
        subcategories: c.subcategories.map((s) => ({
          ...s,
          items: s.items.filter((id) => id !== itemId),
        })),
      }));
      const next = stripped.map((c) => {
        if (c.id !== target.catId) return c;
        if (target.subId) {
          return {
            ...c,
            subcategories: c.subcategories.map((s) =>
              s.id === target.subId ? { ...s, items: [...s.items, itemId] } : s,
            ),
          };
        }
        return { ...c, items: [...c.items, itemId] };
      });
      return { ...l, categories: next };
    });
  };
  const reorderItemDraft = (
    location: { catId: string; subId?: string },
    index: number,
    delta: -1 | 1,
  ) => {
    mutateLayout((l) => ({
      ...l,
      categories: l.categories.map((c) => {
        if (c.id !== location.catId) return c;
        if (location.subId) {
          return {
            ...c,
            subcategories: c.subcategories.map((s) => {
              if (s.id !== location.subId) return s;
              const next = [...s.items];
              const target = index + delta;
              if (target < 0 || target >= next.length) return s;
              const tmp = next[index]!;
              next[index] = next[target]!;
              next[target] = tmp;
              return { ...s, items: next };
            }),
          };
        }
        const nextItems = [...c.items];
        const target = index + delta;
        if (target < 0 || target >= nextItems.length) return c;
        const tmp = nextItems[index]!;
        nextItems[index] = nextItems[target]!;
        nextItems[target] = tmp;
        return { ...c, items: nextItems };
      }),
    }));
  };
  const removeItemDraft = (itemId: number) => {
    mutateLayout((l) => ({
      ...l,
      categories: l.categories.map((c) => ({
        ...c,
        items: c.items.filter((id) => id !== itemId),
        subcategories: c.subcategories.map((s) => ({
          ...s,
          items: s.items.filter((id) => id !== itemId),
        })),
      })),
    }));
    setDraftItems((prev) => (prev ? prev.filter((id) => id !== itemId) : prev));
  };

  /** Reemplaza un id por otro preservando su posición en layout + items. */
  const replaceItemDraft = (oldId: number, newId: number) => {
    if (oldId === newId) return;
    setDraftItems((prev) =>
      prev
        ? Array.from(new Set(prev.map((id) => (id === oldId ? newId : id))))
        : prev,
    );
    mutateLayout((l) => ({
      ...l,
      categories: l.categories.map((c) => ({
        ...c,
        items: c.items.map((id) => (id === oldId ? newId : id)).filter(
          (id, idx, arr) => arr.indexOf(id) === idx,
        ),
        subcategories: c.subcategories.map((s) => ({
          ...s,
          items: s.items.map((id) => (id === oldId ? newId : id)).filter(
            (id, idx, arr) => arr.indexOf(id) === idx,
          ),
        })),
      })),
    }));
  };

  /** Guarda el report_title del template en el backend y refresca la lista local. */
  const updateChartReportTitle = async (
    templateId: number,
    newTitle: string,
  ) => {
    try {
      await savedChartsApi.update(templateId, { report_title: newTitle });
      // Refrescar la lista de templates para ver el cambio reflejado en las cards.
      const rows = await savedChartsApi.list();
      setTemplates(rows);
    } catch (err) {
      alert(err instanceof Error ? err.message : "No se pudo actualizar el título.");
    }
  };

  /** Alterna columnas apiladas ↔ áreas apiladas para un chart. */
  const toggleColumnAreaViewMode = async (tpl: SavedChartTemplate) => {
    const next: "column" | "area" =
      (tpl.view_mode ?? "column") === "area" ? "column" : "area";
    try {
      await savedChartsApi.update(tpl.id, { view_mode: next });
      const rows = await savedChartsApi.list();
      setTemplates(rows);
    } catch (err) {
      alert(
        err instanceof Error
          ? err.message
          : "No se pudo cambiar el tipo de gráfico.",
      );
    }
  };
  const addItemDraft = (
    chartId: number,
    target: { catId: string; subId?: string },
  ) => {
    setDraftItems((prev) =>
      prev && prev.includes(chartId) ? prev : [...(prev ?? []), chartId],
    );
    mutateLayout((l) => {
      const stripped = l.categories.map((c) => ({
        ...c,
        items: c.items.filter((id) => id !== chartId),
        subcategories: c.subcategories.map((s) => ({
          ...s,
          items: s.items.filter((id) => id !== chartId),
        })),
      }));
      const next = stripped.map((c) => {
        if (c.id !== target.catId) return c;
        if (target.subId) {
          return {
            ...c,
            subcategories: c.subcategories.map((s) =>
              s.id === target.subId
                ? { ...s, items: [...s.items, chartId] }
                : s,
            ),
          };
        }
        return { ...c, items: [...c.items, chartId] };
      });
      return { ...l, categories: next };
    });
  };

  const saveLayout = async () => {
    if (!report || !draftLayout) return;
    setSavingLayout(true);
    try {
      await savedChartsApi.updateReport(report.id, {
        layout: draftLayout,
        ...(draftItems ? { items: draftItems } : {}),
        ...(draftAliases
          ? { scenario_aliases: draftAliases.map((s) => s ?? "") }
          : {}),
      });
      await refreshReport();
      setEditing(false);
      setDraftLayout(null);
      setDraftItems(null);
      setDraftAliases(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : "No se pudo guardar.");
    } finally {
      setSavingLayout(false);
    }
  };

  const restoreAuto = async () => {
    if (!report) return;
    if (
      !confirm(
        "Se descartará el layout manual y se volverá al automático por módulo. ¿Continuar?",
      )
    )
      return;
    setSavingLayout(true);
    try {
      await savedChartsApi.updateReport(report.id, { layout: null });
      await refreshReport();
      setEditing(false);
      setDraftLayout(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : "No se pudo restaurar.");
    } finally {
      setSavingLayout(false);
    }
  };

  // ── Persistir rango de años (debounced — guarda al perder foco) ──
  const persistYearRange = async (
    nextFrom: number | null,
    nextTo: number | null,
  ) => {
    if (!report) return;
    // Validar coherencia.
    if (nextFrom != null && nextTo != null && nextFrom > nextTo) {
      alert("El año inicial no puede ser mayor que el año final.");
      return;
    }
    setSavingYears(true);
    try {
      await savedChartsApi.updateReport(report.id, {
        year_from: nextFrom,
        year_to: nextTo,
      });
      await refreshReport();
    } catch (err) {
      alert(err instanceof Error ? err.message : "No se pudo guardar el rango.");
    } finally {
      setSavingYears(false);
    }
  };

  // ── Labels de jobs (para los inputs de renombrar) ──
  const jobLabelById = useMemo(() => {
    const m = new Map<number, string>();
    for (const j of availableJobs) {
      const label = j.display_name?.trim() || j.scenario_name || `Job ${j.id}`;
      m.set(j.id, label);
    }
    return m;
  }, [availableJobs]);

  // ── Export ──
  const canGenerate =
    !!report &&
    maxScenariosNeeded > 0 &&
    globalScenarios.length === maxScenariosNeeded &&
    globalScenarios.every((j) => j != null);

  const handleGenerate = async () => {
    if (!report || !canGenerate) return;
    setGenerating(true);
    setGenerateError(null);
    try {
      const reportHasMultiScenarios = maxScenariosNeeded > 1;
      const flatItems = (report.items ?? [])
        .map((id) => {
          const tpl = templatesById.get(id);
          if (!tpl) return null;
          const job_ids = jobIdsForTemplate(tpl);
          if (job_ids.length === 0) return null;
          const base: {
            template_id: number;
            job_ids: number[];
            scenario_alias_for_title?: string;
          } = { template_id: id, job_ids };
          if (tpl.num_scenarios === 1 && reportHasMultiScenarios) {
            const override = slotOverrides[tpl.id];
            const slotIdx =
              override && override.length > 0 ? (override[0] as number) : 0;
            const alias = scenarioAliases[slotIdx]?.trim();
            base.scenario_alias_for_title =
              alias && alias.length > 0 ? alias : `Escenario ${slotIdx + 1}`;
          }
          return base;
        })
        .filter(
          (
            x,
          ): x is {
            template_id: number;
            job_ids: number[];
            scenario_alias_for_title?: string;
          } => x !== null,
        );

      const overridesForPayload: Record<string, string> = {};
      // Aliases por slot → job_id.
      for (let i = 0; i < globalScenarios.length; i += 1) {
        const jid = globalScenarios[i];
        const alias = scenarioAliases[i]?.trim();
        if (jid != null && alias && alias.length > 0) {
          overridesForPayload[String(jid)] = alias;
        }
      }
      // Renombres explícitos (modal export) sobreescriben aliases.
      for (const jid of globalScenarios) {
        if (jid == null) continue;
        const v = (renameOverrides[jid] ?? "").trim();
        if (v) overridesForPayload[String(jid)] = v;
      }
      const hasOverrides = Object.keys(overridesForPayload).length > 0;
      const basePayload = organizeFolders
        ? {
            items: flatItems,
            fmt,
            organize_by_category: true,
            categories: expandLayoutForExport(
              baseLayout,
              templatesById,
              globalScenarios.filter((j): j is number => j != null),
            ),
          }
        : { items: flatItems, fmt };
      const yearPayload: { year_from?: number; year_to?: number } = {};
      if (yearFrom != null) yearPayload.year_from = yearFrom;
      if (yearTo != null) yearPayload.year_to = yearTo;
      const payload = {
        ...basePayload,
        ...(hasOverrides ? { job_display_overrides: overridesForPayload } : {}),
        ...yearPayload,
      };
      const { blob, filename } = await savedChartsApi.generateReport(payload);
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

  // ── Render ──
  if (loadingReport || loadingTemplates) {
    return (
      <div className="p-6">
        <div className="h-40 animate-pulse rounded-xl border border-slate-800 bg-slate-900/40" />
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="p-6 grid gap-4">
        <h1 className="m-0 text-xl font-bold text-white">
          Reporte no disponible
        </h1>
        <p className="m-0 text-sm text-slate-400">
          {error ?? "No se encontró el reporte solicitado."}
        </p>
        <Link to={paths.reports} className="text-cyan-400 hover:underline">
          ← Volver a Reportes
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 p-6 space-y-6 font-sans">
      {/* ── Header ── */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1 space-y-2">
          <button
            type="button"
            onClick={() => navigate(paths.reports)}
            className="text-xs text-slate-400 hover:text-slate-200"
          >
            ← Volver a Mis reportes
          </button>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="m-0 text-2xl font-bold tracking-tight text-white">
              {report.name}
            </h1>
            {report.is_official ? (
              <span className="inline-flex items-center rounded-full border border-yellow-500/40 bg-yellow-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-yellow-300">
                ★ Oficial
              </span>
            ) : null}
            <span
              className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                report.is_public
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                  : "border-amber-500/30 bg-amber-500/10 text-amber-300"
              }`}
            >
              {report.is_public ? "Público" : "Privado"}
            </span>
            {!report.is_owner ? (
              <span className="rounded-full border border-slate-700 bg-slate-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                de {report.owner_username ?? "otro"}
              </span>
            ) : null}
          </div>
          {report.description ? (
            <p className="m-0 max-w-3xl whitespace-pre-wrap text-sm text-slate-400">
              {report.description}
            </p>
          ) : null}
        </div>
        <div className="flex shrink-0 gap-2 flex-wrap items-center">
          {canEdit ? (
            editing ? (
              <>
                <Button variant="ghost" onClick={cancelEditing} disabled={savingLayout}>
                  Cancelar
                </Button>
                <Button
                  variant="primary"
                  onClick={saveLayout}
                  disabled={savingLayout}
                >
                  {savingLayout ? "Guardando…" : "Guardar organización"}
                </Button>
              </>
            ) : (
              <>
                <Button variant="ghost" onClick={startEditing}>
                  Editar organización
                </Button>
                {report.layout ? (
                  <Button
                    variant="ghost"
                    onClick={restoreAuto}
                    disabled={savingLayout}
                  >
                    Restaurar automático
                  </Button>
                ) : null}
              </>
            )
          ) : null}

          {/* Abrir en el Generador */}
          <Button
            variant="ghost"
            onClick={() => {
              if (!report) return;
              navigate(`${paths.reports}?load=${report.id}`);
            }}
            title="Abrir en el Generador para editar items, escenarios o el reporte completo"
          >
            Editar en generador
          </Button>

          {/* Exportar (popover compacto) */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setExportOpen((v) => !v)}
              className="inline-flex items-center gap-2 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs font-semibold text-emerald-300 hover:bg-emerald-500/20"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Exportar ZIP
              <span className={`text-slate-400 transition-transform ${exportOpen ? "rotate-180" : ""}`}>▾</span>
            </button>
            {exportOpen ? (
              <div className="absolute right-0 top-full z-30 mt-2 w-[300px] rounded-xl border border-slate-800 bg-slate-900/95 p-4 shadow-2xl backdrop-blur-md space-y-3">
                <p className="m-0 text-xs text-slate-500">
                  {(report.items ?? []).length} gráfica
                  {(report.items ?? []).length === 1 ? "" : "s"} ·{" "}
                  {layout.categories.length} categoría
                  {layout.categories.length === 1 ? "" : "s"}
                </p>
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
                      ZIP: 01_Categoria/[01_Sub/]nn_grafica.{fmt}
                    </span>
                  </span>
                </label>
                {globalScenarios.some((j) => j != null) ? (
                  <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-2.5 space-y-2">
                    <button
                      type="button"
                      onClick={() => setRenameOpen((v) => !v)}
                      className="flex w-full items-center justify-between gap-2 text-left"
                    >
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                        Renombrar resultados (solo este export)
                      </span>
                      <span className={`text-slate-500 transition-transform ${renameOpen ? "rotate-180" : ""}`}>▾</span>
                    </button>
                    {renameOpen ? (
                      <div className="space-y-1.5">
                        <p className="m-0 text-[10px] text-slate-500 leading-snug">
                          Cambia cómo aparece cada resultado en los títulos de las gráficas exportadas. No modifica el escenario ni el alias guardado.
                        </p>
                        {globalScenarios.map((jid, idx) => {
                          if (jid == null) return null;
                          const base = jobLabelById.get(jid) ?? `Job ${jid}`;
                          return (
                            <label key={`${idx}-${jid}`} className="grid gap-0.5">
                              <span className="text-[10px] text-slate-500">
                                Escenario {idx + 1} · <span className="text-slate-400">{base}</span>
                              </span>
                              <input
                                type="text"
                                value={renameOverrides[jid] ?? ""}
                                onChange={(e) =>
                                  setRenameOverrides((prev) => ({ ...prev, [jid]: e.target.value }))
                                }
                                placeholder={base}
                                className="rounded border border-slate-700 bg-slate-950/60 px-2 py-1 text-xs text-slate-100 placeholder:text-slate-600"
                              />
                            </label>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                ) : null}
                <div>
                  <p className="m-0 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    Formato
                  </p>
                  <div className="mt-1 inline-flex rounded-lg border border-slate-800 bg-slate-950/40 p-0.5">
                    {(["png", "svg"] as const).map((f) => (
                      <button
                        key={f}
                        type="button"
                        onClick={() => setFmt(f)}
                        className={`rounded-md px-3 py-1.5 text-[11px] font-semibold transition-colors ${
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
                {generateError ? (
                  <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
                    {generateError}
                  </div>
                ) : null}
                <button
                  type="button"
                  onClick={() => void handleGenerate()}
                  disabled={!canGenerate || generating}
                  className="w-full rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {generating ? "Generando…" : "Descargar"}
                </button>
                {!canGenerate && maxScenariosNeeded > 0 ? (
                  <p className="m-0 text-[11px] text-slate-500">
                    Asigna todos los escenarios globales arriba para habilitar la descarga.
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      </div>

      {/* ── Rango de años (filtra dashboard + export) ── */}
      <section className="rounded-xl border border-cyan-500/25 bg-cyan-500/5 p-4 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="m-0 text-sm font-semibold uppercase tracking-wider text-cyan-200">
              Rango de años
            </h2>
            <p className="m-0 mt-1 text-xs text-cyan-200/70">
              Filtra todas las gráficas del dashboard y del ZIP exportado. Deja
              ambos vacíos para mostrar todos los años (predeterminado).
            </p>
          </div>
          {savingYears ? (
            <span className="text-[10px] uppercase tracking-wider text-cyan-300/70">
              Guardando…
            </span>
          ) : null}
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="grid gap-1">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-cyan-300/80">
              Desde
            </span>
            <input
              type="number"
              inputMode="numeric"
              min={1900}
              max={2200}
              value={yearFrom ?? ""}
              onChange={(e) => {
                const raw = e.target.value;
                setYearFrom(raw === "" ? null : Number(raw));
              }}
              onBlur={() => void persistYearRange(yearFrom, yearTo)}
              placeholder="todos"
              className="w-28 rounded border border-cyan-500/40 bg-slate-950/60 px-2 py-1 text-sm text-cyan-100 placeholder:text-cyan-700"
            />
          </label>
          <label className="grid gap-1">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-cyan-300/80">
              Hasta
            </span>
            <input
              type="number"
              inputMode="numeric"
              min={1900}
              max={2200}
              value={yearTo ?? ""}
              onChange={(e) => {
                const raw = e.target.value;
                setYearTo(raw === "" ? null : Number(raw));
              }}
              onBlur={() => void persistYearRange(yearFrom, yearTo)}
              placeholder="todos"
              className="w-28 rounded border border-cyan-500/40 bg-slate-950/60 px-2 py-1 text-sm text-cyan-100 placeholder:text-cyan-700"
            />
          </label>
          {(yearFrom != null || yearTo != null) ? (
            <button
              type="button"
              onClick={() => {
                setYearFrom(null);
                setYearTo(null);
                void persistYearRange(null, null);
              }}
              className="rounded border border-cyan-500/30 bg-cyan-500/10 px-2 py-1 text-[11px] font-medium text-cyan-200 hover:bg-cyan-500/20"
            >
              Limpiar
            </button>
          ) : null}
        </div>
      </section>

      {/* ── Escenarios globales ── */}
      <section className="rounded-xl border border-emerald-500/25 bg-emerald-500/5 p-4 space-y-3">
        <div>
          <h2 className="m-0 text-sm font-semibold uppercase tracking-wider text-emerald-200">
            Escenarios del reporte
          </h2>
          <p className="m-0 mt-1 text-xs text-emerald-200/70">
            {maxScenariosNeeded === 0
              ? "Este reporte no tiene gráficas todavía."
              : `Selecciona ${maxScenariosNeeded} escenario${
                  maxScenariosNeeded === 1 ? "" : "s"
                } para visualizar todas las gráficas del dashboard.`}
          </p>
        </div>
        {maxScenariosNeeded > 0 ? (
          <div
            className="grid gap-2"
            style={{
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            }}
          >
            {Array.from({ length: maxScenariosNeeded }).map((_, idx) => {
              const aliasSource = editing
                ? draftAliases ?? scenarioAliases
                : scenarioAliases;
              const alias = aliasSource[idx]?.trim() || "";
              const label = alias || `Escenario ${idx + 1}`;
              return (
                <div key={idx} className="grid gap-1">
                  <label className="grid gap-1">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-emerald-300/80">
                      {label}
                    </span>
                    <JobSelect
                      value={globalScenarios[idx] ?? null}
                      onChange={(next) => setGlobalScenarioAt(idx, next)}
                      jobs={availableJobs}
                      loading={loadingJobs}
                    />
                  </label>
                  {editing ? (
                    <input
                      type="text"
                      value={(draftAliases ?? [])[idx] ?? ""}
                      onChange={(e) => {
                        const v = e.target.value;
                        setDraftAliases((prev) => {
                          const base = prev ?? [...scenarioAliases];
                          const next = [...base];
                          while (next.length <= idx) next.push("");
                          next[idx] = v;
                          return next;
                        });
                      }}
                      placeholder={`Alias (opcional) · Escenario ${idx + 1}`}
                      className="rounded border border-emerald-500/30 bg-emerald-500/5 px-2 py-1 text-[11px] text-emerald-100 placeholder:text-emerald-300/40"
                    />
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : null}

        <DashboardDefaultScenariosPanel
          reportId={report?.id ?? null}
          current={globalScenarios}
          savedDefaults={
            Array.isArray(report?.default_job_ids)
              ? (report!.default_job_ids as (number | null)[])
              : null
          }
          scenarioAliases={scenarioAliases}
          availableJobs={availableJobs}
          onSaved={async (nextDefaults) => {
            await refreshReport();
            window.alert(
              nextDefaults
                ? "Escenarios predeterminados del reporte actualizados."
                : "Predeterminados eliminados.",
            );
          }}
        />
      </section>

      <div>
        {editing && draftLayout && draftItems ? (
          // ── Modo edición VISUAL: tabs/accordions + charts renderizados + edit controls ──
          <DashboardVisualEditor
            layout={draftLayout}
            items={draftItems}
            templates={templates}
            templatesById={templatesById}
            jobIdsForTemplate={jobIdsForTemplate}
            cardWidthById={cardWidthById}
            setCardWidthById={setCardWidthById}
            activeCategoryId={activeCategoryId}
            setActiveCategoryId={setActiveCategoryId}
            activeSubcatId={activeSubcatId}
            setActiveSubcatId={setActiveSubcatId}
            onSetSubcatDisplay={setSubcatDisplayDraft}
            onRenameCategory={renameCategoryDraft}
            onRenameSub={renameSubDraft}
            onAddCategory={addCategoryDraft}
            onAddSub={addSubDraft}
            onRemoveCategory={removeCategoryDraft}
            onRemoveSub={removeSubDraft}
            onMoveItem={moveItemDraft}
            onReorderItem={reorderItemDraft}
            onRemoveItem={removeItemDraft}
            onAddItem={addItemDraft}
            onReplaceItem={replaceItemDraft}
            onUpdateChartReportTitle={updateChartReportTitle}
            onToggleColumnAreaViewMode={toggleColumnAreaViewMode}
            canEditChartReportTitle={canEditChartReportTitle}
            onMoveCategory={moveCategoryDraft}
            onMoveSub={moveSubDraft}
            onStartCreateNew={startCreateNewChart}
            slotOverrides={slotOverrides}
            onChangeSlotOverride={(templateId, slots) =>
              setSlotOverrides((prev) => {
                const next = { ...prev };
                if (slots == null || slots.length === 0) {
                  delete next[templateId];
                } else {
                  next[templateId] = slots;
                }
                return next;
              })
            }
            globalScenariosLen={Math.max(
              maxScenariosNeeded,
              globalScenarios.length,
            )}
            scenarioAliases={draftAliases ?? scenarioAliases}
            yearFrom={yearFrom}
            yearTo={yearTo}
          />
        ) : (
          // ── Modo lectura: tabs + tarjetas con gráficas renderizadas ──
          <section className="min-w-0 space-y-4">
            {layout.categories.length === 0 ? (
              <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-10 text-center text-sm text-slate-400">
                Este reporte no tiene gráficas asignadas.
              </div>
            ) : (
              <>
                <div className="flex flex-wrap gap-1 rounded-xl border border-slate-800 bg-slate-900/40 p-1">
                  {layout.categories.map((c) => {
                    const total =
                      c.items.length +
                      c.subcategories.reduce(
                        (acc, s) => acc + s.items.length,
                        0,
                      );
                    const active = c.id === activeCategoryId;
                    return (
                      <button
                        key={c.id}
                        type="button"
                        onClick={() => {
                          setActiveCategoryId(c.id);
                          setActiveSubcatId(null);
                        }}
                        className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                          active
                            ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/25"
                            : "text-slate-400 hover:text-slate-200"
                        }`}
                      >
                        {c.label}{" "}
                        <span className="opacity-60">({total})</span>
                      </button>
                    );
                  })}
                </div>

                {(() => {
                  if (!activeCategory) return null;
                  const subcatMode = layout.subcategory_display ?? "tabs";
                  const hasSubcats = activeCategory.subcategories.length > 0;

                  // ── Modo Acordeones: items directos + cada sub como <details open> ──
                  if (subcatMode === "accordions" && hasSubcats) {
                    return (
                      <div className="grid gap-4">
                        {activeCategory.items.length > 0 ? (
                          <div>
                            <h3 className="mt-0 mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                              Sin subcategoría ({activeCategory.items.length})
                            </h3>
                            <ChartGrid
                              chartIds={activeCategory.items}
                              templatesById={templatesById}
                              jobIdsForTemplate={jobIdsForTemplate}
                              cardWidthById={cardWidthById}
                              setCardWidthById={setCardWidthById}
                              resolveAliasSuffix={resolveAliasSuffix}
                              resolveScenarioNames={resolveScenarioNames}
                              yearFrom={yearFrom}
                              yearTo={yearTo}
                            />
                          </div>
                        ) : null}
                        {activeCategory.subcategories.map((s) => (
                          <details
                            key={s.id}
                            open
                            className="rounded-xl border border-slate-800 bg-slate-900/30"
                          >
                            <summary className="cursor-pointer px-4 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-800/40">
                              {s.label}{" "}
                              <span className="opacity-60 text-[11px] font-normal">
                                ({s.items.length})
                              </span>
                            </summary>
                            <div className="p-3">
                              {s.items.length === 0 ? (
                                <div className="rounded-md border border-slate-800 bg-slate-950/30 p-6 text-center text-xs text-slate-500">
                                  Sin gráficas.
                                </div>
                              ) : (
                                <ChartGrid
                                  chartIds={s.items}
                                  templatesById={templatesById}
                                  jobIdsForTemplate={jobIdsForTemplate}
                                  cardWidthById={cardWidthById}
                                  setCardWidthById={setCardWidthById}
                                  resolveAliasSuffix={resolveAliasSuffix}
                                  resolveScenarioNames={resolveScenarioNames}
                                  yearFrom={yearFrom}
                                  yearTo={yearTo}
                                />
                              )}
                            </div>
                          </details>
                        ))}
                      </div>
                    );
                  }

                  // ── Modo Pestañas (default): sub-tabs + grid ──
                  const hasDirectItems = activeCategory.items.length > 0;
                  return (
                    <>
                      {hasSubcats ? (
                        <div className="flex flex-wrap gap-1">
                          {hasDirectItems ? (
                            <button
                              type="button"
                              onClick={() => setActiveSubcatId(GENERAL_SUBCAT_ID)}
                              className={`rounded-md px-3 py-1 text-[11px] font-semibold ${
                                activeSubcatId === GENERAL_SUBCAT_ID
                                  ? "bg-slate-700/60 text-white"
                                  : "text-slate-500 hover:text-slate-300"
                              }`}
                            >
                              General ({activeCategory.items.length})
                            </button>
                          ) : null}
                          {activeCategory.subcategories.map((s) => {
                            const active = s.id === activeSubcatId;
                            return (
                              <button
                                key={s.id}
                                type="button"
                                onClick={() => setActiveSubcatId(s.id)}
                                className={`rounded-md px-3 py-1 text-[11px] font-semibold ${
                                  active
                                    ? "bg-slate-700/60 text-white"
                                    : "text-slate-500 hover:text-slate-300"
                                }`}
                              >
                                {s.label}{" "}
                                <span className="opacity-60">
                                  ({s.items.length})
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      ) : null}
                      {(() => {
                        let chartIds: number[];
                        if (
                          activeSubcatId &&
                          activeSubcatId !== GENERAL_SUBCAT_ID
                        ) {
                          const sub = activeCategory.subcategories.find(
                            (s) => s.id === activeSubcatId,
                          );
                          chartIds = sub?.items ?? [];
                        } else {
                          // "General" o sin subcategorías: items directos.
                          chartIds = [...activeCategory.items];
                        }
                        if (chartIds.length === 0) {
                          return (
                            <div className="w-full rounded-xl border border-slate-800 bg-slate-900/30 p-10 text-center text-sm text-slate-500">
                              No hay gráficas en esta categoría.
                            </div>
                          );
                        }
                        return (
                          <ChartGrid
                            chartIds={chartIds}
                            templatesById={templatesById}
                            jobIdsForTemplate={jobIdsForTemplate}
                            cardWidthById={cardWidthById}
                            setCardWidthById={setCardWidthById}
                            resolveAliasSuffix={resolveAliasSuffix}
                            resolveScenarioNames={resolveScenarioNames}
                            yearFrom={yearFrom}
                            yearTo={yearTo}
                          />
                        );
                      })()}
                    </>
                  );
                })()}
              </>
            )}
          </section>
        )}
      </div>

    </div>
  );
}

// ─── Subcomponente: grid de tarjetas (compartido entre tabs y accordions) ───

/**
 * Panel explícito para configurar los escenarios predeterminados del reporte
 * desde el dashboard. Muestra los persistidos y permite actualizarlos o quitarlos.
 */
function DashboardDefaultScenariosPanel({
  reportId,
  current,
  savedDefaults,
  scenarioAliases,
  availableJobs,
  onSaved,
}: {
  reportId: number | null;
  current: (number | null)[];
  savedDefaults: (number | null)[] | null;
  scenarioAliases: string[];
  availableJobs: SimulationRun[];
  onSaved: (nextDefaults: (number | null)[] | null) => void | Promise<void>;
}) {
  const [saving, setSaving] = useState(false);
  const jobLabel = (jid: number | null | undefined): string => {
    if (jid == null) return "—";
    const j = availableJobs.find((r) => r.id === jid);
    return (
      j?.display_name?.trim() ||
      j?.scenario_name ||
      j?.input_name ||
      `Job ${jid}`
    );
  };
  const aliasLabel = (idx: number): string => {
    const a = scenarioAliases[idx]?.trim();
    return a && a.length > 0 ? a : `Escenario ${idx + 1}`;
  };
  const hasDefaults =
    Array.isArray(savedDefaults) && savedDefaults.some((v) => v != null);
  const sameAsSaved =
    hasDefaults &&
    savedDefaults!.length === current.length &&
    savedDefaults!.every((v, i) => (v ?? null) === (current[i] ?? null));

  const persist = async (next: (number | null)[] | null) => {
    if (!reportId) return;
    setSaving(true);
    try {
      await savedChartsApi.updateReport(reportId, { default_job_ids: next });
      await onSaved(next);
    } catch (err) {
      alert(
        err instanceof Error
          ? err.message
          : "No se pudieron guardar los predeterminados.",
      );
    } finally {
      setSaving(false);
    }
  };

  if (!reportId) return null;

  return (
    <div className="mt-2 rounded-md border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 space-y-1.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="m-0 text-[11px] font-semibold uppercase tracking-wider text-emerald-200">
          Escenarios predeterminados del reporte
          {hasDefaults ? (
            sameAsSaved ? (
              <span className="ml-2 rounded-full bg-emerald-500/15 border border-emerald-500/40 px-1.5 py-0.5 text-[10px] text-emerald-200 normal-case">
                ✓ usando los predeterminados
              </span>
            ) : (
              <span className="ml-2 rounded-full bg-amber-500/10 border border-amber-500/40 px-1.5 py-0.5 text-[10px] text-amber-200 normal-case">
                cambios no guardados
              </span>
            )
          ) : (
            <span className="ml-2 rounded-full bg-slate-800/70 border border-slate-700 px-1.5 py-0.5 text-[10px] text-slate-400 normal-case">
              sin predeterminados
            </span>
          )}
        </p>
        <div className="flex gap-1">
          <button
            type="button"
            disabled={saving}
            onClick={() => {
              if (
                !confirm(
                  "¿Guardar los escenarios seleccionados como predeterminados del reporte?\n\nLa próxima vez que se abra, cargará con estos.",
                )
              )
                return;
              void persist(current);
            }}
            className="rounded border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-200 hover:bg-emerald-500/20 disabled:opacity-50"
          >
            Guardar como predeterminados
          </button>
          {hasDefaults ? (
            <button
              type="button"
              disabled={saving}
              onClick={() => {
                if (!confirm("¿Quitar los escenarios predeterminados del reporte?"))
                  return;
                void persist(null);
              }}
              className="rounded border border-slate-700 px-2 py-0.5 text-[10px] font-semibold text-slate-300 hover:bg-slate-800 disabled:opacity-50"
            >
              Quitar predeterminados
            </button>
          ) : null}
        </div>
      </div>
      {hasDefaults ? (
        <div className="flex flex-wrap gap-1.5 text-[11px]">
          {savedDefaults!.map((jid, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1 rounded border border-emerald-500/20 bg-emerald-500/5 px-1.5 py-0.5 text-emerald-200"
            >
              <span className="text-emerald-300/70 text-[10px] uppercase tracking-wider">
                {aliasLabel(i)}:
              </span>
              <span>{jobLabel(jid)}</span>
            </span>
          ))}
        </div>
      ) : (
        <p className="m-0 text-[11px] text-slate-400">
          Este reporte no tiene escenarios predeterminados. Guarda los
          seleccionados para que la próxima vez se abran así.
        </p>
      )}
    </div>
  );
}

function ChartGrid({
  chartIds,
  templatesById,
  jobIdsForTemplate,
  cardWidthById,
  setCardWidthById,
  resolveAliasSuffix,
  resolveScenarioNames,
  yearFrom,
  yearTo,
}: {
  chartIds: number[];
  templatesById: Map<number, SavedChartTemplate>;
  jobIdsForTemplate: (tpl: SavedChartTemplate) => number[];
  cardWidthById: Record<number, "half" | "full">;
  setCardWidthById: Dispatch<SetStateAction<Record<number, "half" | "full">>>;
  resolveAliasSuffix?: (tpl: SavedChartTemplate) => string | undefined;
  resolveScenarioNames?: (tpl: SavedChartTemplate) => string[] | undefined;
  yearFrom?: number | null;
  yearTo?: number | null;
}) {
  return (
    <div className="flex flex-wrap gap-3">
      {chartIds.map((id, occurrence) => {
        const tpl = templatesById.get(id);
        if (!tpl) return null;
        const jobIds = jobIdsForTemplate(tpl);
        const isMulti =
          tpl.compare_mode === "facet" || tpl.num_scenarios > 1;
        const widthPref = cardWidthById[id] ?? "half";
        const isFull = isMulti || widthPref === "full";
        return (
          <div
            key={`${id}-${occurrence}`}
            className="space-y-2 min-w-0"
            style={{
              flex: isFull ? "0 0 100%" : "1 1 calc(50% - 0.375rem)",
              maxWidth: isFull ? "100%" : "calc(50% - 0.375rem)",
            }}
          >
            <div className="flex items-center justify-end gap-2 text-[11px] text-slate-500">
              {isMulti ? (
                <span className="rounded-md border border-slate-800 bg-slate-900/60 px-2 py-0.5">
                  ancho completo (multi-escenario)
                </span>
              ) : (
                <div
                  role="group"
                  aria-label="Ancho de la gráfica"
                  className="inline-flex rounded-md border border-slate-800 bg-slate-900/60 p-0.5"
                >
                  <button
                    type="button"
                    onClick={() =>
                      setCardWidthById((p) => ({ ...p, [id]: "half" }))
                    }
                    className={`rounded px-2 py-0.5 ${
                      widthPref === "half"
                        ? "bg-cyan-500/15 text-cyan-300"
                        : "text-slate-500 hover:text-slate-300"
                    }`}
                    title="Mostrar la gráfica al 50% del ancho"
                  >
                    50%
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setCardWidthById((p) => ({ ...p, [id]: "full" }))
                    }
                    className={`rounded px-2 py-0.5 ${
                      widthPref === "full"
                        ? "bg-cyan-500/15 text-cyan-300"
                        : "text-slate-500 hover:text-slate-300"
                    }`}
                    title="Mostrar la gráfica al ancho completo"
                  >
                    100%
                  </button>
                </div>
              )}
            </div>
            <DashboardChartCard
              template={tpl}
              jobIds={jobIds}
              compactToolbar
              scenarioAliasSuffix={resolveAliasSuffix?.(tpl)}
              scenarioNames={resolveScenarioNames?.(tpl)}
              yearFrom={yearFrom}
              yearTo={yearTo}
            />
          </div>
        );
      })}
    </div>
  );
}

// ─── Editor visual del dashboard (modo edición) ────────────────────────────

type EditorProps = {
  layout: ReportLayout;
  items: number[];
  templates: SavedChartTemplate[];
  templatesById: Map<number, SavedChartTemplate>;
  jobIdsForTemplate: (tpl: SavedChartTemplate) => number[];
  cardWidthById: Record<number, "half" | "full">;
  setCardWidthById: Dispatch<SetStateAction<Record<number, "half" | "full">>>;
  activeCategoryId: string | null;
  setActiveCategoryId: Dispatch<SetStateAction<string | null>>;
  activeSubcatId: string | null;
  setActiveSubcatId: Dispatch<SetStateAction<string | null>>;
  onSetSubcatDisplay: (mode: "tabs" | "accordions") => void;
  onRenameCategory: (id: string, label: string) => void;
  onRenameSub: (catId: string, subId: string, label: string) => void;
  onAddCategory: () => void;
  onAddSub: (catId: string) => void;
  onRemoveCategory: (id: string) => void;
  onRemoveSub: (catId: string, subId: string) => void;
  onMoveItem: (
    itemId: number,
    target: { catId: string; subId?: string },
  ) => void;
  onReorderItem: (
    location: { catId: string; subId?: string },
    index: number,
    delta: -1 | 1,
  ) => void;
  onRemoveItem: (itemId: number) => void;
  onAddItem: (
    chartId: number,
    target: { catId: string; subId?: string },
  ) => void;
  onReplaceItem: (oldId: number, newId: number) => void;
  onUpdateChartReportTitle: (templateId: number, newTitle: string) => void;
  onToggleColumnAreaViewMode: (tpl: SavedChartTemplate) => void;
  canEditChartReportTitle: (tpl: SavedChartTemplate) => boolean;
  onMoveCategory: (id: string, delta: -1 | 1) => void;
  onMoveSub: (catId: string, subId: string, delta: -1 | 1) => void;
  onStartCreateNew?:
    | ((target: { catId: string; subId?: string } | null) => void)
    | undefined;
  slotOverrides: Record<number, number[]>;
  onChangeSlotOverride: (templateId: number, slots: number[] | null) => void;
  globalScenariosLen: number;
  scenarioAliases: string[];
  yearFrom?: number | null;
  yearTo?: number | null;
};

function DashboardVisualEditor(props: EditorProps) {
  const {
    layout,
    items,
    templates,
    templatesById,
    jobIdsForTemplate,
    cardWidthById,
    setCardWidthById,
    activeCategoryId,
    setActiveCategoryId,
    activeSubcatId,
    setActiveSubcatId,
    onSetSubcatDisplay,
    onRenameCategory,
    onRenameSub,
    onAddCategory,
    onAddSub,
    onRemoveCategory,
    onRemoveSub,
    onMoveItem,
    onReorderItem,
    onRemoveItem,
    onAddItem,
    onReplaceItem,
    onUpdateChartReportTitle,
    onToggleColumnAreaViewMode,
    canEditChartReportTitle,
    onMoveCategory,
    onMoveSub,
    onStartCreateNew,
    slotOverrides,
    onChangeSlotOverride,
    globalScenariosLen,
    scenarioAliases,
    yearFrom,
    yearTo,
  } = props;
  const scenarioLabel = (idx: number): string => {
    const a = scenarioAliases[idx]?.trim();
    return a && a.length > 0 ? a : `Escenario ${idx + 1}`;
  };
  const [editingSlotsId, setEditingSlotsId] = useState<number | null>(null);

  const [replaceTargetId, setReplaceTargetId] = useState<number | null>(null);
  const [titleEditingId, setTitleEditingId] = useState<number | null>(null);
  const [titleDraft, setTitleDraft] = useState<string>("");

  const subcatMode = layout.subcategory_display ?? "tabs";
  const activeCategory = layout.categories.find(
    (c) => c.id === activeCategoryId,
  );
  const hasSubcats = (activeCategory?.subcategories.length ?? 0) > 0;

  // Mostramos TODAS las plantillas accesibles (propias + públicas + oficiales),
  // estén o no ya en el reporte. Las que ya están aparecen marcadas como
  // "ya en reporte · mover" — al hacer clic se mueven a la sección elegida.
  const accessibleAll = templates;

  const [pickerOpen, setPickerOpen] = useState<
    { catId: string; subId?: string } | null
  >(null);

  if (layout.categories.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-8 text-center space-y-3">
        <p className="m-0 text-sm text-slate-300">
          Este reporte no tiene categorías todavía.
        </p>
        <button
          type="button"
          onClick={onAddCategory}
          className="rounded-lg bg-cyan-600 px-4 py-2 text-xs font-semibold text-white hover:bg-cyan-500"
        >
          + Crear primera categoría
        </button>
      </div>
    );
  }

  const renderEditableChart = (
    id: number,
    location: { catId: string; subId?: string },
    index: number,
    sectionLength: number,
  ) => {
    const tpl = templatesById.get(id);
    if (!tpl) return null;
    const jobIds = jobIdsForTemplate(tpl);
    const isMulti =
      tpl.compare_mode === "facet" || tpl.num_scenarios > 1;
    const widthPref = cardWidthById[id] ?? "half";
    const isFull = isMulti || widthPref === "full";
    return (
      <div
        key={`${location.catId}-${location.subId ?? "_"}-${id}-${index}`}
        className="space-y-2 min-w-0"
        style={{
          flex: isFull ? "0 0 100%" : "1 1 calc(50% - 0.375rem)",
          maxWidth: isFull ? "100%" : "calc(50% - 0.375rem)",
        }}
      >
        <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500">
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => onReorderItem(location, index, -1)}
              disabled={index === 0}
              title="Subir"
              className="inline-flex h-6 w-6 items-center justify-center rounded border border-slate-700 hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              ↑
            </button>
            <button
              type="button"
              onClick={() => onReorderItem(location, index, 1)}
              disabled={index === sectionLength - 1}
              title="Bajar"
              className="inline-flex h-6 w-6 items-center justify-center rounded border border-slate-700 hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              ↓
            </button>
            <select
              value=""
              onChange={(e) => {
                const v = e.target.value;
                if (v.startsWith("cat:")) onMoveItem(id, { catId: v.slice(4) });
                else if (v.startsWith("sub:")) {
                  const [catId, subId] = v.slice(4).split("::");
                  if (catId && subId) onMoveItem(id, { catId, subId });
                }
              }}
              className="ml-1 rounded-md border border-slate-700 bg-slate-950/50 px-1.5 py-0.5 text-[10px] text-slate-200"
            >
              <option value="">Mover a…</option>
              {layout.categories.map((c) => (
                <optgroup key={c.id} label={c.label}>
                  {!(c.id === location.catId && !location.subId) ? (
                    <option value={`cat:${c.id}`}>
                      {c.label} (categoría)
                    </option>
                  ) : null}
                  {c.subcategories
                    .filter(
                      (s) =>
                        !(c.id === location.catId && s.id === location.subId),
                    )
                    .map((s) => (
                      <option key={s.id} value={`sub:${c.id}::${s.id}`}>
                        {c.label} → {s.label}
                      </option>
                    ))}
                </optgroup>
              ))}
            </select>
            <button
              type="button"
              onClick={() => setReplaceTargetId(id)}
              title="Reemplazar por otra gráfica guardada"
              className="ml-1 inline-flex h-6 px-2 gap-1 items-center justify-center rounded border border-indigo-500/40 text-[10px] font-semibold text-indigo-300 hover:bg-indigo-500/10"
            >
              <IconSwap size={11} /> Reemplazar
            </button>
            {canEditChartReportTitle(tpl) ? (
              <button
                type="button"
                onClick={() => {
                  setTitleEditingId(id);
                  setTitleDraft(tpl.report_title ?? "");
                }}
                title="Editar título mostrado en reportes"
                className="ml-1 inline-flex h-6 px-2 gap-1 items-center justify-center rounded border border-cyan-500/40 text-[10px] font-semibold text-cyan-300 hover:bg-cyan-500/10"
              >
                <IconPencil size={11} /> Título
              </button>
            ) : null}
            {(tpl.view_mode === "column" ||
              tpl.view_mode === "area" ||
              tpl.view_mode == null) &&
            tpl.compare_mode === "off" &&
            canEditChartReportTitle(tpl) ? (
              <button
                type="button"
                onClick={() => onToggleColumnAreaViewMode(tpl)}
                title={
                  tpl.view_mode === "area"
                    ? "Cambiar a columnas apiladas"
                    : "Cambiar a áreas apiladas"
                }
                className="ml-1 inline-flex h-6 px-2 gap-1 items-center justify-center rounded border border-amber-500/40 text-[10px] font-semibold text-amber-300 hover:bg-amber-500/10"
              >
                {tpl.view_mode === "area" ? "▦ Columnas" : "▲ Áreas"}
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => onRemoveItem(id)}
              title="Quitar del reporte"
              className="ml-1 inline-flex h-6 w-6 items-center justify-center rounded border border-rose-500/40 text-rose-300 hover:bg-rose-500/10"
            >
              ×
            </button>
          </div>
        </div>
        {titleEditingId === id ? (
          <div className="rounded-md border border-cyan-500/30 bg-cyan-500/5 px-2 py-2 space-y-1">
            <p className="m-0 text-[10px] text-slate-400">
              Título usado al renderizar en reportes (vacío → título automático):
            </p>
            <div className="flex gap-1">
              <input
                type="text"
                value={titleDraft}
                onChange={(e) => setTitleDraft(e.target.value)}
                placeholder={tpl.name}
                className="flex-1 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-100"
              />
              <button
                type="button"
                onClick={async () => {
                  await onUpdateChartReportTitle(id, titleDraft);
                  setTitleEditingId(null);
                }}
                className="rounded bg-cyan-600 px-2 py-1 text-[10px] font-semibold text-white hover:bg-cyan-500"
              >
                Guardar
              </button>
              <button
                type="button"
                onClick={() => setTitleEditingId(null)}
                className="rounded border border-slate-700 px-2 py-1 text-[10px] font-semibold text-slate-300 hover:bg-slate-800"
              >
                Cancelar
              </button>
            </div>
          </div>
        ) : tpl.report_title ? (
          <p className="m-0 rounded-md bg-slate-900/60 border border-slate-800 px-2 py-1 text-[10px] text-cyan-200/90">
            <span className="text-slate-500">Título reporte:</span>{" "}
            <span className="font-semibold">{tpl.report_title}</span>
          </p>
        ) : null}
        <div className="flex justify-end text-[11px] text-slate-500">
          {isMulti ? (
            <span className="rounded-md border border-slate-800 bg-slate-900/60 px-2 py-0.5">
              ancho completo (multi-escenario)
            </span>
          ) : (
            <div
              role="group"
              aria-label="Ancho de la gráfica"
              className="inline-flex rounded-md border border-slate-800 bg-slate-900/60 p-0.5"
            >
              <button
                type="button"
                onClick={() =>
                  setCardWidthById((p) => ({ ...p, [id]: "half" }))
                }
                className={`rounded px-2 py-0.5 ${
                  widthPref === "half"
                    ? "bg-cyan-500/15 text-cyan-300"
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                50%
              </button>
              <button
                type="button"
                onClick={() =>
                  setCardWidthById((p) => ({ ...p, [id]: "full" }))
                }
                className={`rounded px-2 py-0.5 ${
                  widthPref === "full"
                    ? "bg-cyan-500/15 text-cyan-300"
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                100%
              </button>
            </div>
          )}
        </div>
        {/* Asignación de escenarios (chip siempre visible + picker colapsable) */}
        {(() => {
          const override = slotOverrides[tpl.id];
          const defaultSlots = Array.from(
            { length: tpl.num_scenarios },
            (_, i) => i,
          );
          const effectiveSlots =
            override && override.length > 0 ? override : defaultSlots;
          return (
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1 rounded-full border border-slate-700 bg-slate-900/60 px-2 py-0.5 text-[10px] font-semibold text-slate-300">
                  <span className="text-slate-500 uppercase tracking-wider">
                    Escenario{effectiveSlots.length === 1 ? "" : "s"}:
                  </span>
                  {effectiveSlots
                    .map((s, i) => (
                      <span key={i} className="text-cyan-300">
                        {scenarioLabel(s)}
                      </span>
                    ))
                    .reduce<React.ReactNode[]>((acc, el, i) => {
                      if (i > 0)
                        acc.push(
                          <span key={`sep-${i}`} className="text-slate-600">
                            ·
                          </span>,
                        );
                      acc.push(el);
                      return acc;
                    }, [])}
                </span>
                <button
                  type="button"
                  onClick={() =>
                    setEditingSlotsId((cur) => (cur === id ? null : id))
                  }
                  className="inline-flex h-6 items-center justify-center gap-1 rounded-md border border-slate-700 px-2 text-[10px] font-semibold text-slate-300 hover:bg-slate-800"
                >
                  {editingSlotsId === id
                    ? "Ocultar asignación"
                    : "Asignar escenarios"}
                </button>
              </div>
              {editingSlotsId === id ? (
                <RowScenarioPicker
                  tpl={tpl}
                  effectiveSlots={effectiveSlots}
                  globalScenariosLen={Math.max(
                    globalScenariosLen,
                    tpl.num_scenarios,
                  )}
                  isOverride={Boolean(override)}
                  onChange={(slots) => onChangeSlotOverride(tpl.id, slots)}
                />
              ) : null}
            </div>
          );
        })()}
        <DashboardChartCard
          template={tpl}
          jobIds={jobIds}
          compactToolbar
          scenarioAliasSuffix={(() => {
            if (tpl.num_scenarios !== 1) return undefined;
            const totalSlots = Math.max(
              scenarioAliases.length,
              globalScenariosLen,
            );
            if (totalSlots <= 1) return undefined;
            const override = slotOverrides[tpl.id];
            const slotIdx =
              override && override.length > 0 ? (override[0] as number) : 0;
            const alias = scenarioAliases[slotIdx]?.trim();
            return alias && alias.length > 0 ? alias : `Escenario ${slotIdx + 1}`;
          })()}
          scenarioNames={(() => {
            const override = slotOverrides[tpl.id];
            const slots =
              override && override.length > 0
                ? override.slice(0, tpl.num_scenarios)
                : Array.from({ length: tpl.num_scenarios }, (_, i) => i);
            return slots.map((s) => {
              const a = scenarioAliases[s]?.trim();
              return a && a.length > 0 ? a : `Escenario ${s + 1}`;
            });
          })()}
          yearFrom={yearFrom}
          yearTo={yearTo}
        />
      </div>
    );
  };

  const renderAddChartButton = (target: { catId: string; subId?: string }) => {
    return (
      <div className="w-full mt-2">
        <button
          type="button"
          onClick={() => setPickerOpen(target)}
          className="w-full rounded-lg border border-dashed border-cyan-500/40 px-3 py-2 text-xs font-semibold text-cyan-300 hover:bg-cyan-500/10"
        >
          + Agregar gráfica a esta sección
        </button>
      </div>
    );
  };

  return (
    <section className="min-w-0 space-y-4">
      {/* Toolbar editor */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 px-3 py-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-amber-300">
          Modo edición
        </span>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Subcategorías:
          </span>
          <div
            role="group"
            className="inline-flex rounded-lg border border-slate-700 bg-slate-900/60 p-0.5"
          >
            <button
              type="button"
              onClick={() => onSetSubcatDisplay("tabs")}
              className={`rounded-md px-2.5 py-1 text-[11px] font-semibold ${
                subcatMode === "tabs"
                  ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/25"
                  : "text-slate-400"
              }`}
            >
              Pestañas
            </button>
            <button
              type="button"
              onClick={() => onSetSubcatDisplay("accordions")}
              className={`rounded-md px-2.5 py-1 text-[11px] font-semibold ${
                subcatMode === "accordions"
                  ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/25"
                  : "text-slate-400"
              }`}
            >
              Acordeones
            </button>
          </div>
        </div>
      </div>

      {/* Tabs de categoría con edición */}
      <div className="flex flex-wrap items-center gap-1 rounded-xl border border-slate-800 bg-slate-900/40 p-1">
        {layout.categories.map((c, cIdx) => {
          const total =
            c.items.length +
            c.subcategories.reduce((acc, s) => acc + s.items.length, 0);
          const active = c.id === activeCategoryId;
          return (
            <div
              key={c.id}
              onClick={() => {
                setActiveCategoryId(c.id);
                setActiveSubcatId(null);
              }}
              className={`flex items-center gap-1 rounded-lg px-2 py-1 cursor-pointer ${
                active
                  ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/25"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onMoveCategory(c.id, -1);
                }}
                disabled={cIdx === 0}
                title="Subir categoría (mueve sus gráficas con ella)"
                className="text-slate-400 hover:text-slate-200 text-xs disabled:opacity-30 disabled:cursor-not-allowed"
              >
                ↑
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onMoveCategory(c.id, 1);
                }}
                disabled={cIdx >= layout.categories.length - 1}
                title="Bajar categoría (mueve sus gráficas con ella)"
                className="text-slate-400 hover:text-slate-200 text-xs disabled:opacity-30 disabled:cursor-not-allowed"
              >
                ↓
              </button>
              <input
                type="text"
                value={c.label}
                onChange={(e) => onRenameCategory(c.id, e.target.value)}
                onClick={(e) => e.stopPropagation()}
                className="bg-transparent border-b border-slate-600 text-current text-xs font-semibold w-32"
              />
              <span className="opacity-60 text-[10px]">({total})</span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onRemoveCategory(c.id);
                }}
                title="Eliminar categoría"
                className="text-rose-400 hover:text-rose-300 text-xs"
              >
                ×
              </button>
            </div>
          );
        })}
        <button
          type="button"
          onClick={onAddCategory}
          className="rounded-lg border border-dashed border-cyan-500/40 px-3 py-1 text-xs font-semibold text-cyan-300 hover:bg-cyan-500/10"
        >
          + Agregar categoría
        </button>
      </div>

      {!activeCategory ? (
        <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-8 text-center text-sm text-slate-500">
          Selecciona una categoría arriba para editarla.
        </div>
      ) : subcatMode === "accordions" ? (
        // ── Modo Acordeones ──
        <div className="grid gap-4">
          {/* Items directos */}
          <div>
            <h3 className="mt-0 mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Sin subcategoría ({activeCategory.items.length})
            </h3>
            {activeCategory.items.length > 0 ? (
              <div className="flex flex-wrap gap-3">
                {activeCategory.items.map((id, idx) =>
                  renderEditableChart(
                    id,
                    { catId: activeCategory.id },
                    idx,
                    activeCategory.items.length,
                  ),
                )}
              </div>
            ) : (
              <div className="rounded-md border border-slate-800 bg-slate-950/30 p-4 text-center text-xs text-slate-500">
                Sin gráficas directas en esta categoría.
              </div>
            )}
            {renderAddChartButton({ catId: activeCategory.id })}
          </div>

          {/* Subcategorías como accordions */}
          {activeCategory.subcategories.map((s, sIdx) => (
            <details
              key={s.id}
              open
              className="rounded-xl border border-slate-800 bg-slate-900/30"
            >
              <summary className="flex cursor-pointer items-center gap-2 px-4 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-800/40">
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    onMoveSub(activeCategory.id, s.id, -1);
                  }}
                  disabled={sIdx === 0}
                  title="Subir subcategoría"
                  className="text-slate-400 hover:text-slate-200 text-xs disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  ↑
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    onMoveSub(activeCategory.id, s.id, 1);
                  }}
                  disabled={sIdx >= activeCategory.subcategories.length - 1}
                  title="Bajar subcategoría"
                  className="text-slate-400 hover:text-slate-200 text-xs disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  ↓
                </button>
                <input
                  type="text"
                  value={s.label}
                  onChange={(e) =>
                    onRenameSub(activeCategory.id, s.id, e.target.value)
                  }
                  onClick={(e) => e.stopPropagation()}
                  className="bg-transparent border-b border-slate-600 text-current"
                />
                <span className="opacity-60 text-[11px] font-normal">
                  ({s.items.length})
                </span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    onRemoveSub(activeCategory.id, s.id);
                  }}
                  className="ml-auto text-rose-400 hover:text-rose-300 text-xs"
                  title="Eliminar subcategoría"
                >
                  Eliminar
                </button>
              </summary>
              <div className="p-3">
                {s.items.length > 0 ? (
                  <div className="flex flex-wrap gap-3">
                    {s.items.map((id, idx) =>
                      renderEditableChart(
                        id,
                        { catId: activeCategory.id, subId: s.id },
                        idx,
                        s.items.length,
                      ),
                    )}
                  </div>
                ) : (
                  <div className="rounded-md border border-slate-800 bg-slate-950/30 p-4 text-center text-xs text-slate-500">
                    Sin gráficas.
                  </div>
                )}
                {renderAddChartButton({
                  catId: activeCategory.id,
                  subId: s.id,
                })}
              </div>
            </details>
          ))}
          {/* Botón para agregar subcategoría al final */}
          <button
            type="button"
            onClick={() => onAddSub(activeCategory.id)}
            className="rounded-lg border border-dashed border-cyan-500/40 px-3 py-2 text-xs font-semibold text-cyan-300 hover:bg-cyan-500/10"
          >
            + Agregar subcategoría
          </button>
        </div>
      ) : (
        // ── Modo Pestañas ──
        <>
          {hasSubcats ? (
            <div className="flex flex-wrap items-center gap-1">
              <button
                type="button"
                onClick={() => setActiveSubcatId(null)}
                className={`rounded-md px-3 py-1 text-[11px] font-semibold ${
                  activeSubcatId == null
                    ? "bg-slate-700/60 text-white"
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                Todas ({activeCategory.items.length})
              </button>
              {activeCategory.subcategories.map((s, sIdx) => {
                const active = s.id === activeSubcatId;
                return (
                  <div
                    key={s.id}
                    className={`flex items-center gap-1 rounded-md px-2 py-0.5 ${
                      active
                        ? "bg-slate-700/60 text-white"
                        : "text-slate-500"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onMoveSub(activeCategory.id, s.id, -1);
                      }}
                      disabled={sIdx === 0}
                      title="Subir subcategoría"
                      className="text-slate-400 hover:text-slate-200 text-[10px] disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onMoveSub(activeCategory.id, s.id, 1);
                      }}
                      disabled={sIdx >= activeCategory.subcategories.length - 1}
                      title="Bajar subcategoría"
                      className="text-slate-400 hover:text-slate-200 text-[10px] disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      ↓
                    </button>
                    <input
                      type="text"
                      value={s.label}
                      onChange={(e) =>
                        onRenameSub(activeCategory.id, s.id, e.target.value)
                      }
                      onClick={(e) => {
                        e.stopPropagation();
                        setActiveSubcatId(s.id);
                      }}
                      className="bg-transparent border-b border-slate-600 text-current text-[11px] font-semibold w-28"
                    />
                    <span className="opacity-60 text-[10px]">
                      ({s.items.length})
                    </span>
                    <button
                      type="button"
                      onClick={() => onRemoveSub(activeCategory.id, s.id)}
                      className="text-rose-400 hover:text-rose-300 text-[10px]"
                      title="Eliminar subcategoría"
                    >
                      ×
                    </button>
                  </div>
                );
              })}
              <button
                type="button"
                onClick={() => onAddSub(activeCategory.id)}
                className="rounded-md border border-dashed border-cyan-500/40 px-2 py-0.5 text-[11px] font-semibold text-cyan-300 hover:bg-cyan-500/10"
              >
                + Agregar subcategoría
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => onAddSub(activeCategory.id)}
              className="rounded-md border border-dashed border-cyan-500/40 px-2 py-1 text-[11px] font-semibold text-cyan-300 hover:bg-cyan-500/10 self-start"
            >
              + Agregar subcategoría
            </button>
          )}
          {(() => {
            // ¿Estamos en sub-tab activa o en "Todas"?
            const sub = activeSubcatId
              ? activeCategory.subcategories.find((s) => s.id === activeSubcatId)
              : null;
            if (sub) {
              return (
                <>
                  {sub.items.length > 0 ? (
                    <div className="flex flex-wrap gap-3">
                      {sub.items.map((id, idx) =>
                        renderEditableChart(
                          id,
                          { catId: activeCategory.id, subId: sub.id },
                          idx,
                          sub.items.length,
                        ),
                      )}
                    </div>
                  ) : (
                    <div className="w-full rounded-xl border border-slate-800 bg-slate-900/30 p-8 text-center text-sm text-slate-500">
                      Sin gráficas en esta subcategoría.
                    </div>
                  )}
                  {renderAddChartButton({
                    catId: activeCategory.id,
                    subId: sub.id,
                  })}
                </>
              );
            }
            // "Todas" o sin subcategoría: items directos.
            return (
              <>
                {activeCategory.items.length > 0 ? (
                  <div className="flex flex-wrap gap-3">
                    {activeCategory.items.map((id, idx) =>
                      renderEditableChart(
                        id,
                        { catId: activeCategory.id },
                        idx,
                        activeCategory.items.length,
                      ),
                    )}
                  </div>
                ) : (
                  <div className="w-full rounded-xl border border-slate-800 bg-slate-900/30 p-8 text-center text-sm text-slate-500">
                    Sin gráficas directas en esta categoría.
                  </div>
                )}
                {renderAddChartButton({ catId: activeCategory.id })}
              </>
            );
          })()}
        </>
      )}
      <ChartPickerModal
        open={replaceTargetId != null}
        onClose={() => setReplaceTargetId(null)}
        title="Reemplazar gráfica"
        templates={templates}
        compatibleWith={
          replaceTargetId != null
            ? templatesById.get(replaceTargetId) ?? null
            : null
        }
        excludeIds={replaceTargetId != null ? [replaceTargetId] : undefined}
        onPick={(tpl) => {
          if (replaceTargetId != null) onReplaceItem(replaceTargetId, tpl.id);
          setReplaceTargetId(null);
        }}
      />

      <ChartPickerModal
        open={pickerOpen != null}
        onClose={() => setPickerOpen(null)}
        title="Agregar gráfica a la sección"
        templates={templates}
        excludeIds={new Set(items)}
        onPick={(tpl) => {
          if (pickerOpen) onAddItem(tpl.id, pickerOpen);
          setPickerOpen(null);
        }}
        onCreateNew={onStartCreateNew ? () => onStartCreateNew(pickerOpen) : undefined}
      />
    </section>
  );
}
