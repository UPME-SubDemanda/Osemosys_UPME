/**
 * Constantes de rutas de la aplicación. Centralizadas para evitar strings hardcodeados.
 * paths.scenarioDetail(id) y paths.resultsDetail(runId) son funciones.
 */
export const paths = {
  home: "/",
  login: "/login",
  app: "/app",
  profile: "/app/profile",
  usersAdmin: "/app/users-admin",
  scenarios: "/app/scenarios",
  scenarioDetail: (id: string | number) => `/app/scenarios/${id}`,
  scenarioTagsAdmin: "/app/scenario-tags-admin",
  changeRequests: "/app/change-requests",
  catalogs: "/app/catalogs",
  visualizationCatalog: "/app/admin/visualization-catalog",
  officialImport: "/app/official-import",
  simulation: "/app/simulation",
  results: "/app/results",
  resultsDetail: (runId: string | number) => `/app/results/${runId}`,
  resultsDataExplorer: (
    runId: string | number,
    filters?: {
      variable_names?: string[];
      technology_prefixes?: string[];
      fuel_prefixes?: string[];
      emission_names?: string[];
    },
  ) => {
    const base = `/app/results/${runId}/data`;
    if (!filters) return base;
    const params = new URLSearchParams();
    const csv = (xs?: string[]) => (xs && xs.length ? xs.join(",") : undefined);
    if (csv(filters.variable_names)) params.set("variable_names", csv(filters.variable_names)!);
    if (csv(filters.technology_prefixes)) params.set("technology_prefixes", csv(filters.technology_prefixes)!);
    if (csv(filters.fuel_prefixes)) params.set("fuel_prefixes", csv(filters.fuel_prefixes)!);
    if (csv(filters.emission_names)) params.set("emission_names", csv(filters.emission_names)!);
    const qs = params.toString();
    return qs ? `${base}?${qs}` : base;
  },
  infeasibilityReport: (runId: string | number) => `/app/simulations/${runId}/infeasibility`,
  reports: "/app/reports",
  reportDashboard: (reportId: string | number) => `/app/reports/${reportId}`,
  history: "/app/history",
} as const;

