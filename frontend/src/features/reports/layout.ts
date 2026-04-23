/**
 * Helpers para el dashboard de reportes:
 *   - `computeAutoLayout`: deriva categorías/subcategorías a partir del MENU
 *     de ChartSelector (módulo, y para Demanda Final, subsector).
 *   - `effectiveLayout`: devuelve el layout almacenado en el reporte si existe;
 *     si no, el layout automático.
 *   - `expandLayoutForExport`: convierte un layout (ids de plantillas) +
 *     escenarios globales en el árbol estructurado que espera el backend
 *     (`ReportCategoryExport[]`).
 */
import type {
  ReportCategoryExport,
  ReportLayout,
  ReportLayoutCategory,
  ReportLayoutSubcategory,
  SavedChartTemplate,
  SavedReport,
} from "@/types/domain";
import {
  getChartLocation,
  getChartModules,
  getChartSubsectors,
  type ChartModuleInfo,
} from "@/shared/charts/ChartSelector";

const UNGROUPED: ChartModuleInfo = {
  id: "_otros",
  label: "Otros",
  emoji: "📁",
};

/** Construye el layout automático a partir de items + plantillas conocidas. */
export function computeAutoLayout(
  items: number[],
  templatesById: Map<number, SavedChartTemplate>,
): ReportLayout {
  const allModules = getChartModules();
  // mapa moduleId → { module, charts: [{ id, subsectorId? }] }
  const byModule = new Map<
    string,
    {
      module: ChartModuleInfo;
      charts: { id: number; subsectorId?: string | undefined }[];
    }
  >();

  for (const id of items) {
    const tpl = templatesById.get(id);
    if (!tpl) continue;
    const loc = getChartLocation(tpl.tipo);
    const mod =
      allModules.find((m) => m.id === loc.moduleId) ?? UNGROUPED;
    const entry = byModule.get(mod.id) ?? { module: mod, charts: [] };
    entry.charts.push({ id, subsectorId: loc.subsectorId });
    byModule.set(mod.id, entry);
  }

  const categories: ReportLayoutCategory[] = [];
  // Respeta el orden del MENU; los desconocidos al final.
  const ordered: { id: string; module: ChartModuleInfo }[] = [];
  for (const m of allModules) {
    if (byModule.has(m.id)) ordered.push({ id: m.id, module: m });
  }
  for (const [id, entry] of byModule.entries()) {
    if (allModules.some((m) => m.id === id)) continue;
    ordered.push({ id, module: entry.module });
  }

  for (const { id, module } of ordered) {
    const entry = byModule.get(id)!;
    const subDefs = getChartSubsectors(module.id);
    if (subDefs.length === 0) {
      // Categoría plana — todos los charts del módulo.
      categories.push({
        id: module.id,
        label: module.label,
        items: entry.charts.map((c) => c.id),
        subcategories: [],
      });
      continue;
    }
    // Con subsectores (Demanda Final): agrupar por subsector y dejar al
    // tope los que no caen en ninguno (defensivo).
    const bySub = new Map<string, number[]>();
    const directItems: number[] = [];
    for (const c of entry.charts) {
      if (c.subsectorId && subDefs.some((s) => s.id === c.subsectorId)) {
        const list = bySub.get(c.subsectorId) ?? [];
        list.push(c.id);
        bySub.set(c.subsectorId, list);
      } else {
        directItems.push(c.id);
      }
    }
    const subcategories: ReportLayoutSubcategory[] = subDefs
      .filter((s) => bySub.has(s.id))
      .map((s) => ({ id: s.id, label: s.label, items: bySub.get(s.id) ?? [] }));
    categories.push({
      id: module.id,
      label: module.label,
      items: directItems,
      subcategories,
    });
  }

  return { categories };
}

/** Layout efectivo: el almacenado si existe; el automático en otro caso. */
export function effectiveLayout(
  report: Pick<SavedReport, "items" | "layout">,
  templatesById: Map<number, SavedChartTemplate>,
): ReportLayout {
  if (report.layout && report.layout.categories.length > 0) {
    return report.layout;
  }
  return computeAutoLayout(report.items ?? [], templatesById);
}

/** Reconcilia el layout con la lista actual de items: ignora ids inexistentes
 * y agrega ids nuevos al final de una categoría "Sin asignar". */
export function reconcileLayout(
  layout: ReportLayout,
  items: number[],
  templatesById: Map<number, SavedChartTemplate>,
): ReportLayout {
  const validIds = new Set(items.filter((id) => templatesById.has(id)));
  const seen = new Set<number>();

  const categories: ReportLayoutCategory[] = layout.categories.map((cat) => ({
    id: cat.id,
    label: cat.label,
    items: cat.items.filter((id) => {
      if (!validIds.has(id) || seen.has(id)) return false;
      seen.add(id);
      return true;
    }),
    subcategories: cat.subcategories.map((sub) => ({
      id: sub.id,
      label: sub.label,
      items: sub.items.filter((id) => {
        if (!validIds.has(id) || seen.has(id)) return false;
        seen.add(id);
        return true;
      }),
    })),
  }));

  const missing = items.filter((id) => validIds.has(id) && !seen.has(id));
  if (missing.length > 0) {
    categories.push({
      id: "_unassigned",
      label: "Sin asignar",
      items: missing,
      subcategories: [],
    });
  }
  // Preserva configuración top-level (p. ej. subcategory_display).
  const next: ReportLayout = { categories };
  if (layout.subcategory_display) {
    next.subcategory_display = layout.subcategory_display;
  }
  return next;
}

/** Construye el árbol que recibe el endpoint `/saved-reports/report` cuando
 * se exporta organizado por categorías. Filtra subcategorías y categorías
 * vacías, y resuelve los `job_ids` por slot a partir de los escenarios globales
 * (slot i → globalScenarios[i] hasta `template.num_scenarios`). */
export function expandLayoutForExport(
  layout: ReportLayout,
  templatesById: Map<number, SavedChartTemplate>,
  globalScenarios: number[],
): ReportCategoryExport[] {
  const resolveJobs = (templateId: number): number[] | null => {
    const tpl = templatesById.get(templateId);
    if (!tpl) return null;
    const jobs: number[] = [];
    for (let i = 0; i < tpl.num_scenarios; i += 1) {
      const j = globalScenarios[i];
      if (j == null) return null;
      jobs.push(j);
    }
    return jobs;
  };

  const out: ReportCategoryExport[] = [];
  for (const cat of layout.categories) {
    const directItems = cat.items
      .map((id) => {
        const job_ids = resolveJobs(id);
        return job_ids ? { template_id: id, job_ids } : null;
      })
      .filter((x): x is { template_id: number; job_ids: number[] } => x !== null);
    const subcats = cat.subcategories
      .map((sub) => ({
        id: sub.id,
        label: sub.label,
        items: sub.items
          .map((id) => {
            const job_ids = resolveJobs(id);
            return job_ids ? { template_id: id, job_ids } : null;
          })
          .filter((x): x is { template_id: number; job_ids: number[] } => x !== null),
      }))
      .filter((s) => s.items.length > 0);
    if (directItems.length === 0 && subcats.length === 0) continue;
    out.push({
      id: cat.id,
      label: cat.label,
      items: directItems,
      subcategories: subcats,
    });
  }
  return out;
}
