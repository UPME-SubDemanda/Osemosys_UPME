/**
 * API para el Data Explorer de resultados de simulación.
 * Expone la tabla `osemosys_output_param_value` en formato wide
 * (años como columnas) con filtros, paginación y export a Excel.
 */
import { httpClient } from "@/shared/api/httpClient";

export type OutputValueWideCell = {
  id: number;
  value: number;
};

export type OutputValueWideRow = {
  group_key: string;
  variable_name: string;
  region_name: string | null;
  technology_name: string | null;
  fuel_name: string | null;
  emission_name: string | null;
  timeslice_name: string | null;
  mode_name: string | null;
  storage_name: string | null;
  season_name: string | null;
  daytype_name: string | null;
  bracket_name: string | null;
  cells: Record<string, OutputValueWideCell>;
};

export type OutputValuesWidePage = {
  items: OutputValueWideRow[];
  total: number;
  offset: number;
  limit: number;
  years: number[];
  has_scalar: boolean;
};

export type OutputWideFacets = {
  variable_names: string[];
  region_names: string[];
  technology_names: string[];
  fuel_names: string[];
  emission_names: string[];
  timeslice_names: string[];
  mode_names: string[];
  storage_names: string[];
};

export type OutputValuesTotals = {
  years: Record<string, number>;
  scalar: number | null;
  row_count: number;
};

export type OutputWideFilters = {
  variable_names?: string[];
  region_names?: string[];
  technology_names?: string[];
  fuel_names?: string[];
  emission_names?: string[];
  timeslice_names?: string[];
  mode_names?: string[];
  storage_names?: string[];
  /** Serializadas como `year:op[:value]` separadas por coma. */
  year_rules?: string;
};

/** Re-export para que el consumidor no tenga que importar de scenariosApi. */
export type { YearRule } from "@/features/scenarios/api/scenariosApi";
export { serializeYearRules } from "@/features/scenarios/api/scenariosApi";

function csv(values?: string[]): string | undefined {
  return values && values.length ? values.join(",") : undefined;
}

function buildParams(filters: OutputWideFilters & Record<string, unknown>) {
  const {
    variable_names,
    region_names,
    technology_names,
    fuel_names,
    emission_names,
    timeslice_names,
    mode_names,
    storage_names,
    year_rules,
    ...rest
  } = filters;
  return {
    ...rest,
    ...(csv(variable_names) ? { variable_names: csv(variable_names) } : {}),
    ...(csv(region_names) ? { region_names: csv(region_names) } : {}),
    ...(csv(technology_names) ? { technology_names: csv(technology_names) } : {}),
    ...(csv(fuel_names) ? { fuel_names: csv(fuel_names) } : {}),
    ...(csv(emission_names) ? { emission_names: csv(emission_names) } : {}),
    ...(csv(timeslice_names) ? { timeslice_names: csv(timeslice_names) } : {}),
    ...(csv(mode_names) ? { mode_names: csv(mode_names) } : {}),
    ...(csv(storage_names) ? { storage_names: csv(storage_names) } : {}),
    ...(year_rules ? { year_rules } : {}),
  };
}

export const resultsDataApi = {
  listOutputValuesWide: (
    jobId: number,
    params: {
      variable_name?: string;
      offset?: number;
      limit?: number;
    } & OutputWideFilters = {},
  ) =>
    httpClient
      .get<OutputValuesWidePage>(`/simulations/${jobId}/output-values/wide`, {
        params: buildParams(params),
      })
      .then((r) => r.data),

  listOutputWideFacets: (
    jobId: number,
    params: {
      variable_name?: string;
      limit_per_column?: number;
    } & OutputWideFilters = {},
  ) =>
    httpClient
      .get<OutputWideFacets>(
        `/simulations/${jobId}/output-values/wide/facets`,
        { params: buildParams(params) },
      )
      .then((r) => r.data),

  getOutputTotals: (
    jobId: number,
    params: { variable_name?: string } & OutputWideFilters = {},
  ) =>
    httpClient
      .get<OutputValuesTotals>(`/simulations/${jobId}/output-values/totals`, {
        params: buildParams(params),
      })
      .then((r) => r.data),

  /** Descarga directa: abre el archivo devolviendo el blob al caller. */
  exportOutputValues: async (
    jobId: number,
    params: { variable_name?: string } & OutputWideFilters = {},
  ): Promise<Blob> => {
    const response = await httpClient.get<Blob>(
      `/simulations/${jobId}/output-values/export`,
      {
        params: buildParams(params),
        responseType: "blob",
      },
    );
    return response.data;
  },
};
