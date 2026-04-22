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
  changeRequests: "/app/change-requests",
  catalogs: "/app/catalogs",
  officialImport: "/app/official-import",
  simulation: "/app/simulation",
  results: "/app/results",
  resultsDetail: (runId: string | number) => `/app/results/${runId}`,
  infeasibilityReport: (runId: string | number) => `/app/simulations/${runId}/infeasibility`,
  reports: "/app/reports",
  reportDashboard: (reportId: string | number) => `/app/reports/${reportId}`,
} as const;

