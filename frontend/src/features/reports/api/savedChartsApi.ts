/**
 * API para plantillas de gráficas guardadas por usuario y generación
 * de reportes (ZIP con una imagen por plantilla).
 */
import { httpClient } from "@/shared/api/httpClient";
import type {
  ReportRequest,
  SavedChartTemplate,
  SavedChartTemplateCreate,
  SavedChartTemplateUpdate,
  SavedReport,
  SavedReportCreate,
  SavedReportUpdate,
} from "@/types/domain";

export const savedChartsApi = {
  async list() {
    const { data } = await httpClient.get<SavedChartTemplate[]>(
      "/saved-chart-templates",
    );
    return data;
  },

  async create(payload: SavedChartTemplateCreate) {
    const { data } = await httpClient.post<SavedChartTemplate>(
      "/saved-chart-templates",
      payload,
    );
    return data;
  },

  async update(templateId: number, payload: SavedChartTemplateUpdate) {
    const { data } = await httpClient.patch<SavedChartTemplate>(
      `/saved-chart-templates/${templateId}`,
      payload,
    );
    return data;
  },

  async remove(templateId: number) {
    await httpClient.delete(`/saved-chart-templates/${templateId}`);
  },

  // ── Reportes guardados (colecciones) ──

  async listReports() {
    const { data } = await httpClient.get<SavedReport[]>("/saved-reports");
    return data;
  },

  async getReport(reportId: number) {
    const { data } = await httpClient.get<SavedReport>(
      `/saved-reports/${reportId}`,
    );
    return data;
  },

  async createReport(payload: SavedReportCreate) {
    const { data } = await httpClient.post<SavedReport>(
      "/saved-reports",
      payload,
    );
    return data;
  },

  async updateReport(reportId: number, payload: SavedReportUpdate) {
    const { data } = await httpClient.patch<SavedReport>(
      `/saved-reports/${reportId}`,
      payload,
    );
    return data;
  },

  async deleteReport(reportId: number) {
    await httpClient.delete(`/saved-reports/${reportId}`);
  },

  async generateReport(
    payload: ReportRequest,
  ): Promise<{ blob: Blob; filename: string }> {
    const response = await httpClient.post("/saved-chart-templates/report", payload, {
      responseType: "blob",
      timeout: 10 * 60 * 1000,
    });
    const blob = response.data as Blob;
    const disposition = response.headers["content-disposition"];
    let filename = "Reporte_OSeMOSYS.zip";
    if (typeof disposition === "string") {
      const match = /filename="?([^";\n]+)"?/i.exec(disposition);
      if (match?.[1]) filename = match[1].trim();
    }
    return { blob, filename };
  },
};
