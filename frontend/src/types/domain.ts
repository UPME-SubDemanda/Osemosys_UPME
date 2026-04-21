/**
 * Tipos del dominio del negocio: escenarios, usuarios, simulaciones, catálogos, etc.
 */
export type ScenarioEditPolicy = "OWNER_ONLY" | "OPEN" | "RESTRICTED";

export type ChangeRequestStatus = "PENDING" | "APPROVED" | "REJECTED";
export type ScenarioPermissionScope = "mine" | "readable" | "editable" | "readonly";

export type RunStatus = "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELLED";
export type SimulationSolver = "highs" | "glpk";
export type SimulationInputMode = "SCENARIO" | "CSV_UPLOAD";

export type CatalogEntity =
  | "parameter"
  | "region"
  | "technology"
  | "fuel"
  | "emission"
  | "solver";

export type User = {
  id: string;
  email: string;
  username: string;
  is_active: boolean;
  can_manage_catalogs: boolean;
  can_import_official_data: boolean;
  can_manage_users: boolean;
};

/** Etiqueta global de escenario (prioridad y color). */
export type ScenarioTag = {
  id: number;
  name: string;
  color: string;
  sort_order: number;
};

export type Scenario = {
  id: number;
  name: string;
  description: string | null;
  owner: string;
  base_scenario_id?: number | null;
  base_scenario_name?: string | null;
  changed_param_names?: string[];
  edit_policy: ScenarioEditPolicy;
  is_template: boolean;
  created_at: string;
  tag?: ScenarioTag | null;
  effective_access?: {
    can_view: boolean;
    is_owner: boolean;
    can_edit_direct: boolean;
    can_propose: boolean;
    can_manage_values: boolean;
  } | null;
};

export type ScenarioPermission = {
  id: number;
  id_scenario: number;
  user_identifier: string;
  user_id: string | null;
  can_edit_direct: boolean;
  can_propose: boolean;
  can_manage_values: boolean;
};

export type ParameterValue = {
  id: number;
  id_parameter: number;
  id_region: number;
  id_solver: number;
  id_technology: number | null;
  id_fuel: number | null;
  id_emission: number | null;
  mode_of_operation: boolean;
  year: number;
  value: number;
  unit: string | null;
};

export type ChangeRequest = {
  id: number;
  id_osemosys_param_value: number;
  created_by: string;
  applied: boolean;
  old_value: number;
  new_value: number;
  status: ChangeRequestStatus;
  created_at: string;
};

export type CatalogItem = {
  id: number;
  entity: CatalogEntity;
  name: string;
  is_active: boolean;
};

export type SimulationRun = {
  id: number;
  scenario_id: number | null;
  scenario_name?: string | null;
  scenario_tag?: ScenarioTag | null;
  user_id: string;
  username?: string | null;
  solver_name: SimulationSolver;
  input_mode: SimulationInputMode;
  input_name?: string | null;
  status: RunStatus;
  progress: number;
  cancel_requested: boolean;
  queue_position: number | null;
  result_ref: string | null;
  error_message: string | null;
  queued_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  /** true si SUCCEEDED pero el solver reportó infactibilidad o hay diagnóstico en el job. */
  is_infeasible_result?: boolean;
  /** True si la simulación se encoló con "correr diagnóstico de infactibilidad automático". */
  run_iis_analysis?: boolean;
  /** Estado del análisis enriquecido de infactibilidad (opcional, on-demand). */
  diagnostic_status?: "NONE" | "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED";
  diagnostic_error?: string | null;
  diagnostic_started_at?: string | null;
  diagnostic_finished_at?: string | null;
  diagnostic_seconds?: number | null;
};

export type SimulationOverview = {
  queued_count: number;
  running_count: number;
  active_count: number;
  total_count: number;
  services_memory_total_bytes: number;
};

export type ConstraintViolation = {
  name: string;
  body: number;
  lower: number | null;
  upper: number | null;
  side: string;
  violation: number;
};

export type VarBoundConflict = {
  name: string;
  lb: number;
  ub: number;
  gap: number;
};

export type IISReport = {
  available: boolean;
  method: string | null;
  constraint_names: string[];
  variable_names: string[];
  unavailable_reason: string | null;
};

export type ParamHit = {
  param: string;
  indices: Record<string, string>;
  value: number | null;
  is_default: boolean;
  default_value?: number | null;
  diff_abs?: number | null;
  deviation_score?: number | null;
};

export type ConstraintAnalysis = {
  name: string;
  constraint_type: string;
  indices: Record<string, string>;
  body: number | null;
  lower: number | null;
  upper: number | null;
  side: string;
  violation: number;
  in_iis: boolean;
  has_mapping: boolean;
  description: string;
  related_params: ParamHit[];
};

export type InfeasibilityOverview = {
  years: number[];
  constraint_types: Record<string, number>;
  variable_types: Record<string, number>;
  techs_or_fuels: Record<string, number>;
  total_constraints: number;
  total_variables: number;
};

export type InfeasibilityDiagnostics = {
  constraint_violations: ConstraintViolation[];
  var_bound_conflicts: VarBoundConflict[];
  // Estado del análisis on-demand (QUEUED/RUNNING/SUCCEEDED/FAILED; ausente = NONE):
  diagnostic_status?: "NONE" | "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED";
  diagnostic_error?: string | null;
  diagnostic_started_at?: string | null;
  diagnostic_finished_at?: string | null;
  diagnostic_seconds?: number | null;
  // Campos enriquecidos (presentes solo si diagnostic_status === 'SUCCEEDED'):
  iis?: IISReport | null;
  overview?: InfeasibilityOverview | null;
  top_suspects?: ParamHit[];
  constraint_analyses?: ConstraintAnalysis[];
  unmapped_constraint_prefixes?: string[];
  csv_dir?: string | null;
};

export type RunResult = {
  job_id: number;
  scenario_id: number | null;
  solver_name: SimulationSolver;
  records_used: number;
  osemosys_param_records: number;
  objective_value: number;
  solver_status: string;
  coverage_ratio: number;
  total_demand: number;
  total_dispatch: number;
  total_unmet: number;
  dispatch: Array<{
    region_id: number;
    year: number;
    technology_name: string | null;
    technology_id: number;
    fuel_name: string | null;
    dispatch: number;
    cost: number;
  }>;
  unmet_demand: Array<{
    region_id: number;
    year: number;
    unmet_demand: number;
  }>;
  new_capacity: Array<{
    region_id: number;
    technology_id: number;
    year: number;
    new_capacity: number;
    technology_name?: string;
  }>;
  annual_emissions: Array<{
    region_id: number;
    year: number;
    annual_emissions: number;
  }>;
  osemosys_inputs_summary: Array<{
    param_name: string;
    year: number | null;
    records: number;
    total_value: number;
  }>;
  stage_times: Record<string, number | string>;
  model_timings: Record<string, number | string>;
  /** Diccionario de solución por variable: lista de { index, value } (tipo HiGHS). */
  sol?: Record<string, Array<{ index: (string | number)[]; value: number }>>;
  /** Variables intermedias: ProductionByTechnology, UseByTechnology, etc. */
  intermediate_variables?: Record<string, Array<{ index: (string | number)[]; value: number }>>;
  infeasibility_diagnostics?: InfeasibilityDiagnostics | null;
};

export type SimulationLog = {
  id: number;
  event_type: string;
  stage: string | null;
  message: string | null;
  progress: number | null;
  created_at: string;
};

export type CsvSimulationResult = {
  solver_name: SimulationSolver;
  objective_value: number;
  solver_status: string;
  coverage_ratio: number;
  total_demand: number;
  total_dispatch: number;
  total_unmet: number;
  dispatch: Array<Record<string, unknown>>;
  unmet_demand: Array<Record<string, unknown>>;
  new_capacity: Array<Record<string, unknown>>;
  annual_emissions: Array<Record<string, unknown>>;
  stage_times: Record<string, number | string>;
  model_timings: Record<string, number | string>;
  sol?: Record<string, Array<{ index: (string | number)[]; value: number }>>;
  intermediate_variables?: Record<string, Array<{ index: (string | number)[]; value: number }>>;
  infeasibility_diagnostics?: InfeasibilityDiagnostics | null;
};

export type ScenarioOperationType = "CLONE_SCENARIO" | "APPLY_EXCEL_CHANGES";
export type ScenarioOperationStatus = "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELLED";

export type ScenarioOperationJob = {
  id: number;
  operation_type: ScenarioOperationType;
  status: ScenarioOperationStatus;
  user_id: string;
  username?: string | null;
  scenario_id: number | null;
  scenario_name?: string | null;
  target_scenario_id: number | null;
  target_scenario_name?: string | null;
  progress: number;
  stage: string | null;
  message: string | null;
  result_json?: Record<string, unknown> | null;
  error_message: string | null;
  queued_at: string;
  started_at?: string | null;
  finished_at?: string | null;
};

export type ScenarioOperationLog = {
  id: number;
  event_type: string;
  stage: string | null;
  message: string | null;
  progress: number | null;
  created_at: string;
};

export type ChartSeries = {
  name: string;
  data: number[];
  color: string;
  stack?: string | null;
};

export type ChartDataResponse = {
  categories: string[];
  series: ChartSeries[];
  title: string;
  yAxisLabel: string;
};

export type SubplotData = {
  year: number;
  categories: string[];
  series: ChartSeries[];
};

export type CompareChartResponse = {
  title: string;
  subplots: SubplotData[];
  yAxisLabel: string;
};

export type CompareMode = "off" | "facet" | "by-year";

export type FacetData = {
  scenario_name: string;
  job_id: number;
  categories: string[];
  series: ChartSeries[];
};

export type CompareChartFacetResponse = {
  title: string;
  facets: FacetData[];
  yAxisLabel: string;
};

export type ChartCatalogItem = {
  id: string;
  label: string;
  variable_default: string;
  has_sub_filtro: boolean;
  has_loc: boolean;
  sub_filtros: string[] | null;
  es_capacidad: boolean;
};

export type ResultSummaryResponse = {
  job_id: number;
  scenario_id: number | null;
  scenario_name: string | null;
  solver_name: string;
  solver_status: string;
  objective_value: number;
  coverage_ratio: number;
  total_demand: number;
  total_dispatch: number;
  total_unmet: number;
  total_co2: number;
};
