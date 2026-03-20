/**
 * API de importación oficial de datos (archivos XLSM).
 * Lista hojas de un workbook y sube archivo con hoja seleccionada.
 */
import { httpClient } from "@/shared/api/httpClient";

export type OfficialImportResult = {
  filename: string;
  imported_at: string;
  imported_by: string;
  total_rows_read: number;
  inserted: number;
  updated: number;
  skipped: number;
  warnings: string[];
  notebook_preprocess?: Record<string, number>;
  notebook_preprocess_error?: string | null;
};

export type WorkbookSheetsResult = {
  filename: string;
  sheets: string[];
};

export type UploadProgressCallback = (percent: number) => void;

export const officialImportApi = {
  async listWorkbookSheets(file: File): Promise<WorkbookSheetsResult> {
    const form = new FormData();
    form.append("file", file);
    const { data } = await httpClient.post<WorkbookSheetsResult>("/official-import/xlsm/sheets", form);
    return data;
  },

  async uploadWorkbook(
    file: File,
    sheetName: string,
    onUploadProgress?: UploadProgressCallback,
    onUploadDone?: () => void,
  ): Promise<OfficialImportResult> {
    const form = new FormData();
    form.append("file", file);
    form.append("sheet_name", sheetName);

    const { data } = await httpClient.post<OfficialImportResult>(
      "/official-import/xlsm",
      form,
      {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 1_800_000,
        onUploadProgress(event) {
          if (event.total && onUploadProgress) {
            onUploadProgress(Math.round((event.loaded * 100) / event.total));
          }
        },
      },
    );
    onUploadDone?.();
    return data;
  },
};
