/**
 * API de simulación OSeMOSYS. Envío de trabajos, listado, cancelación,
 * logs y obtención de resultados (dispatch, unmet, new_capacity, etc.).
 */
import { httpClient } from "@/shared/api/httpClient";
import type { PaginatedResponse } from "@/shared/api/pagination";
import type { 
  CsvSimulationResult,
  ChartCatalogItem, 
  ChartDataResponse, 
  CompareChartFacetResponse, 
  CompareChartResponse, 
  ResultSummaryResponse, 
  RunResult, 
  SimulationLog, 
  SimulationOverview, 
  SimulationRun, 
  SimulationSolver 
} from "@/types/domain";

type ListRunsParams = {
  scope?: "mine" | "global";
  status_filter?: string;
  username?: string;
  scenario_id?: number;
  solver_name?: SimulationSolver;
  cantidad?: number;
  offset?: number;
};

export const simulationApi = {
  async submit(scenarioId: number, solverName: SimulationSolver) {
    const { data } = await httpClient.post<SimulationRun>("/simulations", {
      scenario_id: scenarioId,
      solver_name: solverName,
    });
    return data;
  },

  async submitFromCsv(file: File, solverName: SimulationSolver) {
    const formData = new FormData();
    formData.append("csv_zip", file);
    formData.append("solver_name", solverName);
    const { data } = await httpClient.post<CsvSimulationResult>("/simulations/from-csv", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 10 * 60 * 1000,
    });
    return data;
  },

  async listRuns(params: ListRunsParams = {}) {
    const { data } = await httpClient.get<PaginatedResponse<SimulationRun>>(
      "/simulations",
      { params },
    );
    return data;
  },

  async getOverview() {
    const { data } = await httpClient.get<SimulationOverview>("/simulations/overview");
    return data;
  },

  async getRun(jobId: number) {
    const { data } = await httpClient.get<SimulationRun>(`/simulations/${jobId}`);
    return data;
  },

  async cancel(jobId: number) {
    const { data } = await httpClient.post<SimulationRun>(
      `/simulations/${jobId}/cancel`,
    );
    return data;
  },

  async listLogs(jobId: number, cantidad = 100, offset = 1) {
    const { data } = await httpClient.get<PaginatedResponse<SimulationLog>>(
      `/simulations/${jobId}/logs`,
      { params: { cantidad, offset } },
    );
    return data;
  },

  async getResult(jobId: number) {
    const { data } = await httpClient.get<RunResult>(`/simulations/${jobId}/result`, {
      timeout: 5 * 60 * 1000,
    });
    return data;
  },

  async getResultSummary(jobId: number) {
    const { data } = await httpClient.get<ResultSummaryResponse>(`/visualizations/${jobId}/result-summary`);
    return data;
  },

  async getChartData(jobId: number, params: { tipo: string, un?: string, sub_filtro?: string, loc?: string, variable?: string }) {
    const { data } = await httpClient.get<ChartDataResponse>(`/visualizations/${jobId}/chart-data`, { params });
    return data;
  },

  async getCompareData(params: { job_ids: string, tipo: string, un?: string, years_to_plot?: string, agrupacion?: string, sub_filtro?: string, loc?: string }) {
    const { data } = await httpClient.get<CompareChartResponse>(`/visualizations/chart-data/compare`, { params });
    return data;
  },

  async getCompareFacetData(params: { job_ids: string, tipo: string, un?: string, sub_filtro?: string, loc?: string, variable?: string }) {
    const { data } = await httpClient.get<CompareChartFacetResponse>(`/visualizations/chart-data/compare-facet`, { params });
    return data;
  },

  async getChartCatalog() {
    const { data } = await httpClient.get<ChartCatalogItem[]>("/visualizations/chart-catalog");
    return data;
  },

  async exportAllCharts(jobId: number, un: string = "PJ", fmt: string = "svg") {
    const response = await httpClient.get(`/visualizations/${jobId}/export-all`, {
      params: { un, fmt },
      responseType: "blob",
      timeout: 5 * 60 * 1000,
    });
    return response;
  },

  /** Descarga los datos crudos del job como Excel (osemosys_output_param_value). */
  async exportRawData(jobId: number): Promise<{ blob: Blob; filename: string }> {
    const { data, headers } = await httpClient.get(`/visualizations/${jobId}/export-raw`, {
      responseType: "blob",
      timeout: 10 * 60 * 1000,
    });
    const blob = data as Blob;
    const disposition = headers["content-disposition"];
    let filename = `Resultados_Crudos_Job_${jobId}.xlsx`;
    if (typeof disposition === "string") {
      const match = /filename="?([^";\n]+)"?/i.exec(disposition);
      if (match?.[1]) filename = match[1].trim();
    }
    return { blob, filename };
  },
};
