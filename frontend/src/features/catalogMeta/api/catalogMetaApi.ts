/**
 * API de administración del catálogo editable de visualización (Fase 3).
 *
 * Endpoints (gated por `can_manage_catalogs`):
 *   POST /catalog-meta/invalidate-cache
 *   GET/POST/PATCH/DELETE /catalog-meta/colors
 */
import { httpClient } from "@/shared/api/httpClient";

export type ColorGroup = "fuel" | "pwr" | "sector" | "emission" | "family";

export const ALLOWED_COLOR_GROUPS: ColorGroup[] = [
  "fuel",
  "pwr",
  "sector",
  "emission",
  "family",
];

export type ColorItem = {
  id: number;
  key: string;
  group: ColorGroup;
  color_hex: string;
  description: string | null;
  sort_order: number;
  updated_at: string;
};

export type ColorListResponse = {
  items: ColorItem[];
  total: number;
  allowed_groups: ColorGroup[];
};

export type ColorCreate = {
  key: string;
  group: ColorGroup;
  color_hex: string;
  description?: string | null;
  sort_order?: number;
};

export type ColorUpdate = {
  color_hex?: string;
  description?: string | null;
  sort_order?: number;
};

export const catalogMetaApi = {
  invalidateCache: () =>
    httpClient.post<{ status: string }>("/catalog-meta/invalidate-cache").then((r) => r.data),

  listColors: (group?: ColorGroup) =>
    httpClient
      .get<ColorListResponse>("/catalog-meta/colors", {
        params: group ? { group } : undefined,
      })
      .then((r) => r.data),

  createColor: (payload: ColorCreate) =>
    httpClient.post<ColorItem>("/catalog-meta/colors", payload).then((r) => r.data),

  updateColor: (id: number, payload: ColorUpdate) =>
    httpClient.patch<ColorItem>(`/catalog-meta/colors/${id}`, payload).then((r) => r.data),

  deleteColor: (id: number) =>
    httpClient.delete<void>(`/catalog-meta/colors/${id}`).then((r) => r.data),

  upsertColor: (payload: ColorCreate) =>
    httpClient.post<ColorItem>("/catalog-meta/colors/upsert", payload).then((r) => r.data),

  // Labels ------------------------------------------------------------------
  listLabels: (params: {
    search?: string;
    category?: string;
    offset?: number;
    limit?: number;
  } = {}) =>
    httpClient
      .get<LabelListResponse>("/catalog-meta/labels", { params })
      .then((r) => r.data),

  createLabel: (payload: LabelCreate) =>
    httpClient.post<LabelItem>("/catalog-meta/labels", payload).then((r) => r.data),

  updateLabel: (id: number, payload: LabelUpdate) =>
    httpClient.patch<LabelItem>(`/catalog-meta/labels/${id}`, payload).then((r) => r.data),

  deleteLabel: (id: number) =>
    httpClient.delete<void>(`/catalog-meta/labels/${id}`).then((r) => r.data),

  upsertLabel: (payload: LabelCreate) =>
    httpClient.post<LabelItem>("/catalog-meta/labels/upsert", payload).then((r) => r.data),

  codeUsage: (codes: string[]) =>
    httpClient
      .get<{ items: Record<string, { count: number; chart_tipos: string[]; chart_labels: string[] }> }>(
        "/catalog-meta/usage",
        { params: { codes: codes.join(",") } },
      )
      .then((r) => r.data),
};

export type LabelItem = {
  id: number;
  code: string;
  label_es: string;
  label_en: string | null;
  category: string | null;
  sort_order: number;
  updated_at: string;
};

export type LabelListResponse = {
  items: LabelItem[];
  total: number;
  offset: number;
  limit: number;
  categories: string[];
};

export type LabelCreate = {
  code: string;
  label_es: string;
  label_en?: string | null;
  category?: string | null;
  sort_order?: number;
};

export type LabelUpdate = {
  label_es?: string;
  label_en?: string | null;
  category?: string | null;
  sort_order?: number;
};

// ---------------------------------------------------------------------------
// Audit / historial
// ---------------------------------------------------------------------------

export type AuditEntry = {
  id: number;
  table_name: string;
  row_id: number | null;
  action: "INSERT" | "UPDATE" | "DELETE" | string;
  diff_json: Record<string, unknown> | unknown[] | null;
  changed_by_username: string | null;
  changed_at: string;
};

export type AuditListResponse = {
  items: AuditEntry[];
  total: number;
  offset: number;
  limit: number;
  tables: string[];
};

// ---------------------------------------------------------------------------
// Sectores (prefijo tech → sector)
// ---------------------------------------------------------------------------

export type SectorMappingItem = {
  id: number;
  tech_prefix: string;
  sector_name: string;
  sort_order: number;
  updated_at: string;
};

export type SectorMappingListResponse = {
  items: SectorMappingItem[];
  total: number;
};

export type SectorMappingCreate = {
  tech_prefix: string;
  sector_name: string;
  sort_order?: number;
};

export type SectorMappingUpdate = {
  sector_name?: string;
  sort_order?: number;
};

export const catalogMetaSectorApi = {
  list: () =>
    httpClient.get<SectorMappingListResponse>("/catalog-meta/sectors").then((r) => r.data),
  create: (payload: SectorMappingCreate) =>
    httpClient.post<SectorMappingItem>("/catalog-meta/sectors", payload).then((r) => r.data),
  update: (id: number, payload: SectorMappingUpdate) =>
    httpClient.patch<SectorMappingItem>(`/catalog-meta/sectors/${id}`, payload).then((r) => r.data),
  delete: (id: number) =>
    httpClient.delete<void>(`/catalog-meta/sectors/${id}`).then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Familias tecnológicas
// ---------------------------------------------------------------------------

export type TechFamilyItem = {
  id: number;
  family_code: string;
  tech_prefix: string;
  sort_order: number;
  updated_at: string;
};

export type TechFamilyListResponse = {
  items: TechFamilyItem[];
  total: number;
  families: string[];
};

export type TechFamilyCreate = {
  family_code: string;
  tech_prefix: string;
  sort_order?: number;
};

export type TechFamilyBulkAdd = {
  family_code: string;
  tech_prefixes: string[];
};

export const catalogMetaTechFamilyApi = {
  list: (family_code?: string) =>
    httpClient
      .get<TechFamilyListResponse>("/catalog-meta/tech-families", {
        params: family_code ? { family_code } : undefined,
      })
      .then((r) => r.data),
  create: (payload: TechFamilyCreate) =>
    httpClient.post<TechFamilyItem>("/catalog-meta/tech-families", payload).then((r) => r.data),
  bulkAdd: (payload: TechFamilyBulkAdd) =>
    httpClient.post<TechFamilyItem[]>("/catalog-meta/tech-families/bulk", payload).then((r) => r.data),
  update: (id: number, payload: { sort_order?: number }) =>
    httpClient.patch<TechFamilyItem>(`/catalog-meta/tech-families/${id}`, payload).then((r) => r.data),
  delete: (id: number) =>
    httpClient.delete<void>(`/catalog-meta/tech-families/${id}`).then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Módulos + Submódulos del ChartSelector
// ---------------------------------------------------------------------------

export type ChartSubmoduleItem = {
  id: number;
  module_id: number;
  code: string;
  label: string;
  icon: string | null;
  sort_order: number;
  is_visible: boolean;
  updated_at: string;
};

export type ChartModuleItem = {
  id: number;
  code: string;
  label: string;
  icon: string | null;
  sort_order: number;
  is_visible: boolean;
  updated_at: string;
  submodules: ChartSubmoduleItem[];
  chart_count: number;
};

export type ChartModulesTreeResponse = { items: ChartModuleItem[] };

export type ChartModuleCreate = {
  code: string;
  label: string;
  icon?: string | null;
  sort_order?: number;
  is_visible?: boolean;
};

export type ChartModuleUpdate = {
  label?: string;
  icon?: string | null;
  sort_order?: number;
  is_visible?: boolean;
};

export type ChartSubmoduleCreate = {
  module_id: number;
  code: string;
  label: string;
  icon?: string | null;
  sort_order?: number;
  is_visible?: boolean;
};

export type ChartSubmoduleUpdate = {
  module_id?: number;
  label?: string;
  icon?: string | null;
  sort_order?: number;
  is_visible?: boolean;
};

export const catalogMetaModuleApi = {
  tree: () =>
    httpClient.get<ChartModulesTreeResponse>("/catalog-meta/modules").then((r) => r.data),
  createModule: (payload: ChartModuleCreate) =>
    httpClient.post<ChartModuleItem>("/catalog-meta/modules", payload).then((r) => r.data),
  updateModule: (id: number, payload: ChartModuleUpdate) =>
    httpClient.patch<ChartModuleItem>(`/catalog-meta/modules/${id}`, payload).then((r) => r.data),
  deleteModule: (id: number) =>
    httpClient.delete<void>(`/catalog-meta/modules/${id}`).then((r) => r.data),
  createSubmodule: (payload: ChartSubmoduleCreate) =>
    httpClient.post<ChartSubmoduleItem>("/catalog-meta/submodules", payload).then((r) => r.data),
  updateSubmodule: (id: number, payload: ChartSubmoduleUpdate) =>
    httpClient.patch<ChartSubmoduleItem>(`/catalog-meta/submodules/${id}`, payload).then((r) => r.data),
  deleteSubmodule: (id: number) =>
    httpClient.delete<void>(`/catalog-meta/submodules/${id}`).then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Chart config + sub-filtros (3.3.F + 3.3.H)
// ---------------------------------------------------------------------------

export type ChartSubfilterItem = {
  id: number;
  chart_id: number;
  group_label: string | null;
  code: string;
  display_label: string | null;
  sort_order: number;
  default_selected: boolean;
};

export type ChartConfigItem = {
  id: number;
  tipo: string;
  module_id: number;
  submodule_id: number | null;
  label_titulo: string;
  label_figura: string | null;
  variable_default: string;
  filtro_kind: string;
  filtro_params_json: Record<string, unknown> | null;
  agrupar_por_default: string;
  agrupaciones_permitidas_json: string[] | null;
  color_fn_key: string;
  flags_json: Record<string, unknown> | null;
  msg_sin_datos: string | null;
  data_explorer_filters_json: Record<string, unknown> | null;
  is_visible: boolean;
  sort_order: number;
  subfilters: ChartSubfilterItem[];
  updated_at: string;
};

export type ChartConfigListResponse = { items: ChartConfigItem[]; total: number };

export type ChartConfigUpdate = Partial<
  Omit<ChartConfigItem, "id" | "tipo" | "subfilters" | "updated_at">
>;

export const catalogMetaChartApi = {
  list: (moduleId?: number) =>
    httpClient
      .get<ChartConfigListResponse>("/catalog-meta/charts", {
        params: moduleId !== undefined ? { module_id: moduleId } : undefined,
      })
      .then((r) => r.data),
  update: (id: number, payload: ChartConfigUpdate) =>
    httpClient.patch<ChartConfigItem>(`/catalog-meta/charts/${id}`, payload).then((r) => r.data),
  remove: (id: number) =>
    httpClient.delete<void>(`/catalog-meta/charts/${id}`).then((r) => r.data),
  createSubfilter: (payload: {
    chart_id: number;
    group_label?: string | null;
    code: string;
    display_label?: string | null;
    sort_order?: number;
    default_selected?: boolean;
  }) =>
    httpClient
      .post<ChartSubfilterItem>("/catalog-meta/chart-subfilters", payload)
      .then((r) => r.data),
  updateSubfilter: (
    id: number,
    payload: Partial<Omit<ChartSubfilterItem, "id" | "chart_id" | "code">>,
  ) =>
    httpClient
      .patch<ChartSubfilterItem>(`/catalog-meta/chart-subfilters/${id}`, payload)
      .then((r) => r.data),
  deleteSubfilter: (id: number) =>
    httpClient.delete<void>(`/catalog-meta/chart-subfilters/${id}`).then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Variable units (3.3.E)
// ---------------------------------------------------------------------------

export type DisplayUnitEntry = {
  code: string;
  label: string;
  factor: number;
};

export type VariableUnitItem = {
  id: number;
  variable_name: string;
  unit_base: string;
  display_units_json: DisplayUnitEntry[] | null;
  updated_at: string;
};

export type VariableUnitListResponse = { items: VariableUnitItem[]; total: number };

export const catalogMetaUnitApi = {
  list: () =>
    httpClient.get<VariableUnitListResponse>("/catalog-meta/variable-units").then((r) => r.data),
  create: (payload: {
    variable_name: string;
    unit_base: string;
    display_units_json?: DisplayUnitEntry[] | null;
  }) =>
    httpClient.post<VariableUnitItem>("/catalog-meta/variable-units", payload).then((r) => r.data),
  update: (id: number, payload: { unit_base?: string; display_units_json?: DisplayUnitEntry[] | null }) =>
    httpClient.patch<VariableUnitItem>(`/catalog-meta/variable-units/${id}`, payload).then((r) => r.data),
  delete: (id: number) =>
    httpClient.delete<void>(`/catalog-meta/variable-units/${id}`).then((r) => r.data),
};

// ---------------------------------------------------------------------------
// Audit (historial)
// ---------------------------------------------------------------------------

export const catalogMetaAuditApi = {
  list: (params: {
    table_name?: string;
    action?: string;
    row_id?: number;
    offset?: number;
    limit?: number;
  } = {}) =>
    httpClient
      .get<AuditListResponse>("/catalog-meta/audit", { params })
      .then((r) => r.data),
};
