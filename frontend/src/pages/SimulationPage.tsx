/**
 * SimulationPage - Encolar y gestionar simulaciones OSeMOSYS
 *
 * Funcionalidades:
 * - Seleccionar escenario y solver (HiGHS/GLPK) para encolar una simulación
 * - Ver historial de jobs con filtro por estado (QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED)
 * - Polling automático cada 3s cuando hay jobs activos (en cola o ejecutando)
 * - Cancelar jobs en curso
 * - Ver logs de cada ejecución en modal
 *
 * Endpoints usados:
 * - scenariosApi.listScenarios()
 * - simulationApi.listRuns(), submit(), cancel(), listLogs()
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useCurrentUser } from "@/app/providers/useCurrentUser";
import { useToast } from "@/app/providers/useToast";
import { scenariosApi } from "@/features/scenarios/api/scenariosApi";
import type { UdcConfig, UdcMultiplierEntry } from "@/features/scenarios/api/scenariosApi";
import { simulationApi } from "@/features/simulation/api/simulationApi";
import { InfeasibilityDiagnosticsPanel } from "@/features/simulation/components/InfeasibilityDiagnosticsPanel";
import { getSimulationRunStatusDisplay } from "@/features/simulation/simulationRunStatus";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { DataTable } from "@/shared/components/DataTable";
import { Modal } from "@/shared/components/Modal";
import { TextField } from "@/shared/components/TextField";
import { paths } from "@/routes/paths";
import type {
  CsvSimulationResult,
  RunResult,
  Scenario,
  SimulationLog,
  SimulationOverview,
  SimulationRun,
  SimulationSolver,
} from "@/types/domain";

const ACTIVE_STATUSES = new Set(["QUEUED", "RUNNING"]);
const CSV_PREVIEW_LIMIT = 50;

function getSolverStatusVariant(status: string) {
  const normalized = status.toLowerCase();
  if (normalized.includes("optimal")) return "success" as const;
  if (normalized.includes("infeasible") || normalized.includes("infactible")) return "danger" as const;
  return "warning" as const;
}

function getSolverLabel(solverName: SimulationSolver) {
  return solverName === "highs" ? "HiGHS" : "GLPK";
}

function formatCsvValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") {
    return value.toLocaleString(undefined, {
      maximumFractionDigits: Number.isInteger(value) ? 0 : 4,
    });
  }
  if (typeof value === "boolean") return value ? "Sí" : "No";
  if (Array.isArray(value) || typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function toCsvSimulationResult(result: RunResult): CsvSimulationResult {
  const base: CsvSimulationResult = {
    solver_name: result.solver_name,
    objective_value: result.objective_value,
    solver_status: result.solver_status,
    coverage_ratio: result.coverage_ratio,
    total_demand: result.total_demand,
    total_dispatch: result.total_dispatch,
    total_unmet: result.total_unmet,
    dispatch: result.dispatch,
    unmet_demand: result.unmet_demand,
    new_capacity: result.new_capacity,
    annual_emissions: result.annual_emissions,
    stage_times: result.stage_times,
    model_timings: result.model_timings,
  };
  return {
    ...base,
    ...(result.sol ? { sol: result.sol } : {}),
    ...(result.intermediate_variables ? { intermediate_variables: result.intermediate_variables } : {}),
    ...(result.infeasibility_diagnostics ? { infeasibility_diagnostics: result.infeasibility_diagnostics } : {}),
  };
}

function getCsvColumns(rows: Array<Record<string, unknown>>, preferredColumns: string[]) {
  const presentPreferred = preferredColumns.filter((column) =>
    rows.some((row) => Object.prototype.hasOwnProperty.call(row, column)),
  );
  const extraColumns = Array.from(
    new Set(rows.flatMap((row) => Object.keys(row)).filter((column) => !presentPreferred.includes(column))),
  );
  return [...presentPreferred, ...extraColumns];
}

function CsvMetricCard({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "danger" | "success" }) {
  return (
    <div
      style={{
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: 12,
        padding: 14,
        background:
          tone === "danger"
            ? "rgba(127,29,29,0.18)"
            : tone === "success"
              ? "rgba(20,83,45,0.18)"
              : "rgba(255,255,255,0.02)",
      }}
    >
      <div style={{ fontSize: 12, opacity: 0.7 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700 }}>{value}</div>
    </div>
  );
}

function TablePagination({
  page,
  totalPages,
  onPrevious,
  onNext,
}: {
  page: number;
  totalPages: number;
  onPrevious: () => void;
  onNext: () => void;
}) {
  if (totalPages <= 1) return null;

  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
      <small style={{ opacity: 0.78 }}>
        Página {page} de {totalPages}
      </small>
      <div style={{ display: "flex", gap: 8 }}>
        <Button variant="ghost" onClick={onPrevious} disabled={page <= 1} type="button">
          Anterior
        </Button>
        <Button variant="ghost" onClick={onNext} disabled={page >= totalPages} type="button">
          Siguiente
        </Button>
      </div>
    </div>
  );
}

function CsvResultTableSection({
  title,
  rows,
  preferredColumns,
  emptyMessage,
  defaultOpen = false,
}: {
  title: string;
  rows: Array<Record<string, unknown>>;
  preferredColumns: string[];
  emptyMessage: string;
  defaultOpen?: boolean;
}) {
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(rows.length / CSV_PREVIEW_LIMIT));
  const pageStart = (page - 1) * CSV_PREVIEW_LIMIT;
  const visibleRows = rows.slice(pageStart, pageStart + CSV_PREVIEW_LIMIT);
  const columns = getCsvColumns(visibleRows, preferredColumns);

  useEffect(() => {
    setPage(1);
  }, [rows.length, title]);

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  return (
    <details
      open={defaultOpen}
      style={{
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: 12,
        padding: 12,
        background: "rgba(255,255,255,0.02)",
      }}
    >
      <summary style={{ cursor: "pointer", fontWeight: 600 }}>
        {title} ({rows.length})
      </summary>
      <div style={{ display: "grid", gap: 10, marginTop: 10 }}>
        {rows.length ? (
          <>
            <small style={{ opacity: 0.78 }}>
              Mostrando {pageStart + 1} a {pageStart + visibleRows.length} de {rows.length} filas.
            </small>
            <TablePagination
              page={page}
              totalPages={totalPages}
              onPrevious={() => setPage((current) => Math.max(1, current - 1))}
              onNext={() => setPage((current) => Math.min(totalPages, current + 1))}
            />
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr>
                    {columns.map((column) => (
                      <th
                        key={column}
                        style={{
                          textAlign: "left",
                          padding: "6px 8px",
                          borderBottom: "1px solid rgba(255,255,255,0.2)",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {visibleRows.map((row, rowIndex) => (
                    <tr key={`${title}-${rowIndex}`}>
                      {columns.map((column) => (
                        <td
                          key={column}
                          style={{
                            padding: "6px 8px",
                            borderBottom: "1px solid rgba(255,255,255,0.08)",
                            verticalAlign: "top",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {formatCsvValue(row[column])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <small style={{ opacity: 0.78 }}>{emptyMessage}</small>
        )}
      </div>
    </details>
  );
}

export function SimulationPage() {
  const { user } = useCurrentUser();
  const { push } = useToast();
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedScenario, setSelectedScenario] = useState("");
  const [runs, setRuns] = useState<SimulationRun[]>([]);
  const [overview, setOverview] = useState<SimulationOverview | null>(null);
  const [loadingScenarios, setLoadingScenarios] = useState(false);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [errorRuns, setErrorRuns] = useState<string | null>(null);
  const [logsByJob, setLogsByJob] = useState<Record<number, SimulationLog[]>>({});
  const [logsOpenForJob, setLogsOpenForJob] = useState<number | null>(null);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [statusFilter, setStatusFilter] = useState<SimulationRun["status"] | "ALL">("ALL");
  const [usernameFilter, setUsernameFilter] = useState("");
  const [solverName, setSolverName] = useState<SimulationSolver>("highs");
  const [csvSolverName, setCsvSolverName] = useState<SimulationSolver>("highs");
  const [csvZipFile, setCsvZipFile] = useState<File | null>(null);
  const [csvSubmitting, setCsvSubmitting] = useState(false);
  const [csvResult, setCsvResult] = useState<CsvSimulationResult | null>(null);
  const [csvResultOpen, setCsvResultOpen] = useState(false);
  const [csvTrackedJobId, setCsvTrackedJobId] = useState<number | null>(null);
  const [csvResultSourceJobId, setCsvResultSourceJobId] = useState<number | null>(null);
  const [csvLoadingResultForJobId, setCsvLoadingResultForJobId] = useState<number | null>(null);
  const [cancellingJobId, setCancellingJobId] = useState<number | null>(null);

  const [udcConfig, setUdcConfig] = useState<UdcConfig | null>(null);
  const [udcOpen, setUdcOpen] = useState(false);
  const [udcSaving, setUdcSaving] = useState(false);
  const [udcNewTech, setUdcNewTech] = useState("");
  const [udcNewValue, setUdcNewValue] = useState("0");

  const formatBytes = useCallback((bytes: number) => {
    if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let value = bytes;
    let unitIndex = 0;
    while (value >= 1024 && unitIndex < units.length - 1) {
      value /= 1024;
      unitIndex += 1;
    }
    return `${value.toFixed(value >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
  }, []);

  useEffect(() => {
    const id = Number(selectedScenario);
    if (!id) { setUdcConfig(null); return; }
    void scenariosApi.getUdcConfig(id).then(setUdcConfig).catch(() => setUdcConfig(null));
  }, [selectedScenario]);

  async function saveUdcConfig() {
    const id = Number(selectedScenario);
    if (!id || !udcConfig) return;
    setUdcSaving(true);
    try {
      const saved = await scenariosApi.updateUdcConfig(id, udcConfig);
      setUdcConfig(saved);
      push("Configuración UDC guardada.", "success");
    } catch (e) {
      push(e instanceof Error ? e.message : "Error guardando UDC.", "error");
    } finally {
      setUdcSaving(false);
    }
  }

  /** Recarga el historial de jobs; usa statusFilter si no es ALL */
  const refreshRuns = useCallback(async () => {
    setLoadingRuns(true);
    setErrorRuns(null);
    try {
      const params = {
        scope: "global" as const,
        cantidad: 50,
        offset: 1,
        ...(statusFilter === "ALL" ? {} : { status_filter: statusFilter }),
        ...(usernameFilter.trim() ? { username: usernameFilter.trim() } : {}),
      };
      const [res, overviewRes] = await Promise.all([simulationApi.listRuns(params), simulationApi.getOverview()]);
      setRuns(res.data);
      setOverview(overviewRes);
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "No se pudo cargar el historial de simulaciones.";
      setErrorRuns(message);
      push(message, "error");
    } finally {
      setLoadingRuns(false);
    }
  }, [push, statusFilter, usernameFilter]);

  useEffect(() => {
    if (!user) return;
    setLoadingScenarios(true);
    void scenariosApi
      .listScenarios({ cantidad: 200, offset: 1 })
      .then((res) => setScenarios(res.data))
      .catch(() => setScenarios([]))
      .finally(() => setLoadingScenarios(false));
  }, [user]);

  // Polling cada 3s mientras haya jobs en cola o ejecutando
  useEffect(() => {
    const shouldPoll = runs.some((run) => ACTIVE_STATUSES.has(run.status));
    if (!shouldPoll) return;
    const timer = window.setInterval(() => {
      void refreshRuns();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [refreshRuns, runs]);

  useEffect(() => {
    if (!user) return;
    void refreshRuns();
  }, [refreshRuns, user]);

  useEffect(() => {
    if (!csvTrackedJobId) return;
    const trackedRun = runs.find((run) => run.id === csvTrackedJobId);
    if (!trackedRun) return;

    if (trackedRun.status === "SUCCEEDED") {
      if (csvLoadingResultForJobId === csvTrackedJobId || csvResultSourceJobId === csvTrackedJobId) {
        return;
      }
      setCsvLoadingResultForJobId(csvTrackedJobId);
      void simulationApi
        .getResult(csvTrackedJobId)
        .then((result) => {
          setCsvResult(toCsvSimulationResult(result));
          setCsvResultSourceJobId(csvTrackedJobId);
          setCsvResultOpen(true);
          push(`Resultados del job CSV ${csvTrackedJobId} disponibles.`, "success");
        })
        .catch((error) => {
          const detail =
            error instanceof Error ? error.message : "No se pudieron cargar los resultados del job CSV.";
          push(detail, "error");
        })
        .finally(() => {
          setCsvLoadingResultForJobId(null);
          setCsvTrackedJobId(null);
        });
      return;
    }

    if (trackedRun.status === "FAILED") {
      push(
        trackedRun.error_message
          ? `La simulación CSV falló: ${trackedRun.error_message}`
          : "La simulación CSV falló.",
        "error",
      );
      setCsvTrackedJobId(null);
      return;
    }

    if (trackedRun.status === "CANCELLED") {
      push("La simulación CSV fue cancelada.", "info");
      setCsvTrackedJobId(null);
    }
  }, [csvLoadingResultForJobId, csvResultSourceJobId, csvTrackedJobId, push, runs]);

  /** Encola una simulación para el escenario y solver seleccionados */
  async function runSimulation() {
    const scenarioId = Number(selectedScenario);
    if (!scenarioId) {
      push("Selecciona un escenario antes de ejecutar.", "error");
      return;
    }
    setSubmitting(true);
    try {
      await simulationApi.submit(scenarioId, solverName);
      push("Simulación encolada correctamente.", "success");
      await refreshRuns();
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Error enviando simulación.";
      push(detail, "error");
    } finally {
      setSubmitting(false);
    }
  }

  /** Cancela un job en curso; actualiza UI optimista antes de confirmar */
  async function cancelSimulation(jobId: number) {
    setCancellingJobId(jobId);
    setRuns((prev) =>
      prev.map((r) => (r.id === jobId ? { ...r, status: "CANCELLED" as const } : r))
    );
    try {
      await simulationApi.cancel(jobId);
      push(`Simulación ${jobId} cancelada.`, "info");
      await refreshRuns();
    } catch (error) {
      const detail = error instanceof Error ? error.message : "No se pudo cancelar.";
      push(detail, "error");
      await refreshRuns();
    } finally {
      setCancellingJobId(null);
    }
  }

  /** Carga los logs de un job y abre el modal */
  async function loadLogs(jobId: number) {
    try {
      setLoadingLogs(true);
      const res = await simulationApi.listLogs(jobId, 100, 1);
      setLogsByJob((prev) => ({ ...prev, [jobId]: res.data }));
      setLogsOpenForJob(jobId);
    } catch {
      push("No se pudieron cargar logs del job.", "error");
    } finally {
      setLoadingLogs(false);
    }
  }

  async function runCsvSimulation() {
    if (!csvZipFile) {
      push("Selecciona un archivo ZIP con los CSV antes de ejecutar.", "error");
      return;
    }
    setCsvSubmitting(true);
    setCsvResultOpen(false);
    setCsvResult(null);
    setCsvResultSourceJobId(null);
    setCsvTrackedJobId(null);
    try {
      const job = await simulationApi.submitFromCsv(csvZipFile, csvSolverName);
      setCsvTrackedJobId(job.id);
      setRuns((prev) => [job, ...prev.filter((run) => run.id !== job.id)]);
      push(`Simulación desde CSV encolada como job ${job.id}.`, "success");
      await refreshRuns();
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Error ejecutando simulación desde CSV.";
      push(detail, "error");
    } finally {
      setCsvSubmitting(false);
    }
  }

  function downloadCsvResultJson() {
    if (!csvResult) return;
    const blob = new Blob([JSON.stringify(csvResult, null, 2)], { type: "application/json" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "simulation_from_csv_result.json";
    link.click();
    window.URL.revokeObjectURL(url);
  }

  // Filtrado por estado seleccionado (ALL = sin filtrar)
  const filteredRuns = useMemo(() => {
    if (statusFilter === "ALL") return runs;
    return runs.filter((run) => run.status === statusFilter);
  }, [runs, statusFilter]);

  const selectedLogs = logsOpenForJob ? logsByJob[logsOpenForJob] ?? [] : [];

  return (
    <section style={{ display: "grid", gap: 14 }}>
      <article className="pageSection" style={{ display: "grid", gap: 12 }}>
        <h1 style={{ margin: 0 }}>Simulación OSeMOSYS</h1>
        <small style={{ opacity: 0.78 }}>
          Encola ejecuciones y revisa la cola global.
        </small>
        <div
          style={{
            display: "grid",
            gap: 10,
            gridTemplateColumns: "minmax(260px, 1fr) minmax(180px, 240px) auto auto",
            alignItems: "end",
          }}
        >
          <label className="field" style={{ margin: 0 }}>
            <span className="field__label">Escenario</span>
            <select
              className="field__input"
              value={selectedScenario}
              onChange={(e) => setSelectedScenario(e.target.value)}
              disabled={loadingScenarios}
            >
              <option value="">{loadingScenarios ? "Cargando escenarios..." : "Selecciona..."}</option>
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field" style={{ margin: 0 }}>
            <span className="field__label">Solver</span>
            <select
              className="field__input"
              value={solverName}
              onChange={(e) => setSolverName(e.target.value as SimulationSolver)}
            >
              <option value="highs">HiGHS</option>
              <option value="glpk">GLPK</option>
            </select>
          </label>
          <Button variant="primary" onClick={runSimulation} disabled={submitting || !selectedScenario}>
            {submitting ? "Encolando..." : "Ejecutar simulación"}
          </Button>
          <Button variant="ghost" onClick={refreshRuns} disabled={loadingRuns}>
            Refrescar estado
          </Button>
        </div>
      </article>

      <article className="pageSection" style={{ display: "grid", gap: 12 }}>
        <div style={{ display: "grid", gap: 4 }}>
          <h2 style={{ margin: 0 }}>Simulación desde CSV</h2>
          <small style={{ opacity: 0.78 }}>
            Sube un ZIP con CSV ya procesados (`YEAR.csv`, `REGION.csv`, `TECHNOLOGY.csv`, etc.) para encolar una corrida persistida y consultarla luego en el historial.
          </small>
        </div>
        <div
          style={{
            display: "grid",
            gap: 10,
            gridTemplateColumns: "minmax(280px, 1fr) minmax(180px, 240px) auto",
            alignItems: "end",
          }}
        >
          <label className="field" style={{ margin: 0 }}>
            <span className="field__label">ZIP de CSV</span>
            <input
              className="field__input"
              type="file"
              accept=".zip,application/zip"
              onChange={(e) => setCsvZipFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <label className="field" style={{ margin: 0 }}>
            <span className="field__label">Solver</span>
            <select
              className="field__input"
              value={csvSolverName}
              onChange={(e) => setCsvSolverName(e.target.value as SimulationSolver)}
            >
              <option value="highs">HiGHS</option>
              <option value="glpk">GLPK</option>
            </select>
          </label>
          <Button variant="primary" onClick={runCsvSimulation} disabled={csvSubmitting || !csvZipFile}>
            {csvSubmitting ? "Encolando..." : "Ejecutar desde CSV"}
          </Button>
        </div>
        {csvZipFile ? (
          <small style={{ opacity: 0.78 }}>
            Archivo seleccionado: <strong>{csvZipFile.name}</strong>
          </small>
        ) : null}
        {csvResult ? (
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <Button variant="ghost" onClick={() => setCsvResultOpen(true)}>
              Ver últimos resultados
            </Button>
          </div>
        ) : null}
        {csvTrackedJobId ? (
          <small style={{ opacity: 0.78 }}>
            Job CSV en seguimiento: <strong>#{csvTrackedJobId}</strong>. Se abrirá automáticamente cuando termine.
          </small>
        ) : null}
      </article>

      {selectedScenario && udcConfig ? (
        <article className="pageSection" style={{ display: "grid", gap: 10 }}>
          <div
            style={{ display: "flex", justifyContent: "space-between", alignItems: "center", cursor: "pointer" }}
            onClick={() => setUdcOpen(!udcOpen)}
          >
            <h2 style={{ margin: 0 }}>Configuración UDC (Restricciones definidas por usuario)</h2>
            <span style={{ fontSize: 18 }}>{udcOpen ? "▲" : "▼"}</span>
          </div>

          {udcOpen ? (
            <div style={{ display: "grid", gap: 12 }}>
              <div style={{ display: "flex", gap: 16, alignItems: "end", flexWrap: "wrap" }}>
                <label className="field" style={{ margin: 0, width: 200 }}>
                  <span className="field__label">Tipo de restricción (UDCTag)</span>
                  <select
                    className="field__input"
                    value={udcConfig.tag_value}
                    onChange={(e) =>
                      setUdcConfig({ ...udcConfig, tag_value: Number(e.target.value) as 0 | 1 })
                    }
                  >
                    <option value={0}>0 — Desigualdad (≤)</option>
                    <option value={1}>1 — Igualdad (=)</option>
                  </select>
                </label>
              </div>

              {udcConfig.multipliers.map((mult, mIdx) => (
                <div key={mIdx} style={{ border: "1px solid rgba(255,255,255,0.15)", borderRadius: 8, padding: 12, display: "grid", gap: 8 }}>
                  <div style={{ display: "flex", gap: 12, alignItems: "end" }}>
                    <label className="field" style={{ margin: 0, width: 220 }}>
                      <span className="field__label">Tipo de multiplicador</span>
                      <select
                        className="field__input"
                        value={mult.type}
                        onChange={(e) => {
                          const updated = [...udcConfig.multipliers];
                          updated[mIdx] = { ...mult, type: e.target.value as UdcMultiplierEntry["type"] };
                          setUdcConfig({ ...udcConfig, multipliers: updated });
                        }}
                      >
                        <option value="TotalCapacity">TotalCapacity</option>
                        <option value="NewCapacity">NewCapacity</option>
                        <option value="Activity">Activity</option>
                      </select>
                    </label>
                    <Button
                      variant="ghost"
                      onClick={() => {
                        const updated = udcConfig.multipliers.filter((_, i) => i !== mIdx);
                        setUdcConfig({ ...udcConfig, multipliers: updated });
                      }}
                    >
                      Eliminar multiplicador
                    </Button>
                  </div>

                  <div style={{ maxHeight: 300, overflow: "auto" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                      <thead>
                        <tr>
                          <th style={{ textAlign: "left", padding: "4px 8px", borderBottom: "1px solid rgba(255,255,255,0.2)" }}>Tecnología</th>
                          <th style={{ textAlign: "right", padding: "4px 8px", borderBottom: "1px solid rgba(255,255,255,0.2)" }}>Valor</th>
                          <th style={{ width: 40 }}></th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(mult.tech_dict).map(([tech, val]) => (
                          <tr key={tech}>
                            <td style={{ padding: "2px 8px" }}>{tech}</td>
                            <td style={{ padding: "2px 8px", textAlign: "right" }}>
                              <input
                                type="number"
                                step="any"
                                style={{ width: 100, textAlign: "right" }}
                                value={val}
                                onChange={(e) => {
                                  const updated = [...udcConfig.multipliers];
                                  updated[mIdx] = {
                                    ...mult,
                                    tech_dict: { ...mult.tech_dict, [tech]: Number(e.target.value) },
                                  };
                                  setUdcConfig({ ...udcConfig, multipliers: updated });
                                }}
                              />
                            </td>
                            <td>
                              <button
                                type="button"
                                style={{ cursor: "pointer", border: "none", background: "none", color: "rgba(248,113,113,0.9)" }}
                                onClick={() => {
                                  const { [tech]: _, ...rest } = mult.tech_dict;
                                  const updated = [...udcConfig.multipliers];
                                  updated[mIdx] = { ...mult, tech_dict: rest };
                                  setUdcConfig({ ...udcConfig, multipliers: updated });
                                }}
                              >
                                ✕
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div style={{ display: "flex", gap: 8, alignItems: "end" }}>
                    <label className="field" style={{ margin: 0, flex: 1 }}>
                      <span className="field__label">Agregar tecnología</span>
                      <input
                        className="field__input"
                        placeholder="Ej: PWRNUC"
                        value={udcNewTech}
                        onChange={(e) => setUdcNewTech(e.target.value)}
                      />
                    </label>
                    <label className="field" style={{ margin: 0, width: 120 }}>
                      <span className="field__label">Valor</span>
                      <input
                        className="field__input"
                        type="number"
                        step="any"
                        value={udcNewValue}
                        onChange={(e) => setUdcNewValue(e.target.value)}
                      />
                    </label>
                    <Button
                      variant="ghost"
                      onClick={() => {
                        if (!udcNewTech.trim()) return;
                        const updated = [...udcConfig.multipliers];
                        updated[mIdx] = {
                          ...mult,
                          tech_dict: { ...mult.tech_dict, [udcNewTech.trim()]: Number(udcNewValue) },
                        };
                        setUdcConfig({ ...udcConfig, multipliers: updated });
                        setUdcNewTech("");
                        setUdcNewValue("0");
                      }}
                    >
                      Agregar
                    </Button>
                  </div>
                </div>
              ))}

              <div style={{ display: "flex", gap: 8 }}>
                <Button
                  variant="ghost"
                  onClick={() =>
                    setUdcConfig({
                      ...udcConfig,
                      multipliers: [
                        ...udcConfig.multipliers,
                        { type: "TotalCapacity", tech_dict: {} },
                      ],
                    })
                  }
                >
                  + Agregar multiplicador
                </Button>
                <Button variant="primary" onClick={saveUdcConfig} disabled={udcSaving}>
                  {udcSaving ? "Guardando..." : "Guardar configuración UDC"}
                </Button>
              </div>
            </div>
          ) : null}
        </article>
      ) : null}

      <article className="pageSection" style={{ display: "grid", gap: 10 }}>
        <h2 style={{ margin: 0 }}>Resumen operativo</h2>
        <div style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))" }}>
          {[
            { label: "En cola", value: overview?.queued_count ?? 0 },
            { label: "Ejecutando", value: overview?.running_count ?? 0 },
            { label: "Activas", value: overview?.active_count ?? 0 },
            { label: "Total visibles", value: overview?.total_count ?? runs.length },
            { label: "RAM total", value: formatBytes(overview?.services_memory_total_bytes ?? 0) },
          ].map((item) => (
            <div key={item.label} style={{ border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, padding: 14 }}>
              <div style={{ fontSize: 12, opacity: 0.7 }}>{item.label}</div>
              <div style={{ fontSize: 24, fontWeight: 700 }}>{item.value}</div>
            </div>
          ))}
        </div>
      </article>

      <article className="pageSection" style={{ display: "grid", gap: 10 }}>
        <div className="toolbarRow">
          <h2 style={{ margin: 0 }}>Cola global y ejecuciones</h2>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <TextField
              label="Filtrar por usuario"
              value={usernameFilter}
              onChange={(e) => setUsernameFilter(e.target.value)}
              placeholder="username"
            />
            <label className="field" style={{ width: 220 }}>
              <span className="field__label">Filtrar por estado</span>
              <select
                className="field__input"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as SimulationRun["status"] | "ALL")}
              >
                <option value="ALL">Todos</option>
                <option value="QUEUED">En cola</option>
                <option value="RUNNING">En ejecución</option>
                <option value="SUCCEEDED">Exitosa</option>
                <option value="FAILED">Fallida</option>
                <option value="CANCELLED">Cancelada</option>
              </select>
            </label>
          </div>
        </div>
        {loadingRuns ? (
          <div style={{ display: "grid", gap: 8 }}>
            <div className="skeletonLine" />
            <div className="skeletonLine" />
            <div className="skeletonLine" />
          </div>
        ) : null}
        {!loadingRuns && errorRuns ? (
          <div style={{ border: "1px solid rgba(239,68,68,0.4)", borderRadius: 12, padding: 12 }}>
            <strong>Error cargando jobs</strong>
            <p style={{ marginBottom: 0 }}>{errorRuns}</p>
          </div>
        ) : null}
        {!loadingRuns && !errorRuns && filteredRuns.length === 0 ? (
          <div style={{ border: "1px dashed rgba(255,255,255,0.2)", borderRadius: 12, padding: 12 }}>
            No hay jobs para el filtro seleccionado.
          </div>
        ) : null}
        <DataTable
          rows={filteredRuns}
          rowKey={(r) => String(r.id)}
          columns={[
            { key: "id", header: "ID de ejecución", render: (r) => r.id },
            {
              key: "scenario",
              header: "Escenario",
              render: (r) =>
                r.scenario_name ??
                (r.input_mode === "CSV_UPLOAD"
                  ? r.input_name ?? "CSV upload"
                  : r.scenario_id === null
                    ? "—"
                    : `#${r.scenario_id}`),
            },
            { key: "user", header: "Usuario", render: (r) => r.username ?? r.user_id },
            {
              key: "solver",
              header: "Solver",
              render: (r) => (r.solver_name === "highs" ? "HiGHS" : "GLPK"),
            },
            {
              key: "status",
              header: "Estado",
              render: (r) => {
                const { variant, label } = getSimulationRunStatusDisplay(r);
                return <Badge variant={variant}>{label}</Badge>;
              },
            },
            { key: "progress", header: "Progreso", render: (r) => `${r.progress}%` },
            {
              key: "queue",
              header: "Cola",
              render: (r) => (r.queue_position ?? "—"),
            },
            {
              key: "queued_at",
              header: "Encolado",
              render: (r) => new Date(r.queued_at).toLocaleString(),
            },
            {
              key: "started_at",
              header: "Inicio",
              render: (r) => (r.started_at ? new Date(r.started_at).toLocaleString() : "—"),
            },
            {
              key: "finished_at",
              header: "Fin",
              render: (r) => (r.finished_at ? new Date(r.finished_at).toLocaleString() : "—"),
            },
            {
              key: "error",
              header: "Error",
              render: (r) =>
                r.error_message ? (
                  <span style={{ color: "rgba(248,113,113,0.9)" }}>{r.error_message}</span>
                ) : (
                  "—"
                ),
            },
            {
              key: "logs",
              header: "Registros",
              render: (r) => (
                <button
                  type="button"
                  className="btn btn--ghost"
                  onClick={() => void loadLogs(r.id)}
                >
                  Ver registros
                </button>
              ),
            },
            {
              key: "go",
              header: "Resultados",
              render: (r) => (
                <div style={{ display: "flex", gap: 6 }}>
                  <Link className="btn btn--ghost" to={paths.resultsDetail(r.id)}>
                    Abrir
                  </Link>
                  {ACTIVE_STATUSES.has(r.status) ? (
                    <Button
                      variant="ghost"
                      onClick={() => void cancelSimulation(r.id)}
                      disabled={cancellingJobId === r.id}
                    >
                      {cancellingJobId === r.id ? "Cancelando…" : "Cancelar"}
                    </Button>
                  ) : null}
                </div>
              ),
            },
          ]}
          searchableText={(r) => `${r.id} ${r.scenario_name ?? ""} ${r.input_name ?? ""} ${r.username ?? ""} ${r.status} ${r.queue_position ?? ""}`}
        />
      </article>

      <Modal
        open={csvResultOpen && csvResult !== null}
        title="Resultados de simulación desde CSV"
        onClose={() => setCsvResultOpen(false)}
        wide
        footer={
          csvResult ? (
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, flexWrap: "wrap" }}>
              <Button variant="ghost" onClick={downloadCsvResultJson}>
                Descargar JSON completo
              </Button>
              <Button variant="primary" onClick={() => setCsvResultOpen(false)}>
                Cerrar
              </Button>
            </div>
          ) : undefined
        }
      >
        {csvResult ? (
          <div style={{ display: "grid", gap: 16 }}>
            <div
              style={{
                display: "flex",
                gap: 10,
                alignItems: "center",
                justifyContent: "space-between",
                flexWrap: "wrap",
              }}
            >
              <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                <Badge variant={getSolverStatusVariant(csvResult.solver_status)}>{csvResult.solver_status}</Badge>
                <span>Solver: {getSolverLabel(csvResult.solver_name)}</span>
              </div>
            </div>

            <div
              style={{
                display: "grid",
                gap: 10,
                gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              }}
            >
              <CsvMetricCard
                label="Estado del solver"
                value={csvResult.solver_status}
                tone={
                  getSolverStatusVariant(csvResult.solver_status) === "danger"
                    ? "danger"
                    : getSolverStatusVariant(csvResult.solver_status) === "success"
                      ? "success"
                      : "default"
                }
              />
              <CsvMetricCard label="Valor objetivo" value={csvResult.objective_value.toLocaleString()} />
              <CsvMetricCard label="Cobertura" value={`${(csvResult.coverage_ratio * 100).toFixed(2)}%`} />
              <CsvMetricCard label="Demanda total" value={csvResult.total_demand.toLocaleString()} />
              <CsvMetricCard label="Unmet total" value={csvResult.total_unmet.toLocaleString()} />
            </div>

            <div style={{ display: "grid", gap: 12 }}>
              <CsvResultTableSection
                title="Dispatch"
                rows={csvResult.dispatch}
                preferredColumns={["region", "region_id", "year", "technology_name", "technology_id", "fuel_name", "dispatch", "cost"]}
                emptyMessage="No se generaron filas de dispatch."
                defaultOpen
              />
              <CsvResultTableSection
                title="New Capacity"
                rows={csvResult.new_capacity}
                preferredColumns={["region", "region_id", "year", "technology_name", "technology_id", "new_capacity"]}
                emptyMessage="No se generaron filas de nueva capacidad."
              />
              <CsvResultTableSection
                title="Unmet Demand"
                rows={csvResult.unmet_demand}
                preferredColumns={["region", "region_id", "year", "unmet_demand"]}
                emptyMessage="No se registró demanda no atendida."
              />
              <CsvResultTableSection
                title="Annual Emissions"
                rows={csvResult.annual_emissions}
                preferredColumns={["region", "region_id", "year", "emission_name", "annual_emissions"]}
                emptyMessage="No se generaron emisiones anuales."
              />
            </div>

            <InfeasibilityDiagnosticsPanel result={csvResult} scenarioParams={{ state: "none" }} />
          </div>
        ) : null}
      </Modal>

      <Modal
        open={logsOpenForJob !== null}
        title={logsOpenForJob ? `Registros de la ejecución ${logsOpenForJob}` : "Registros"}
        onClose={() => setLogsOpenForJob(null)}
      >
        {loadingLogs ? (
          <div style={{ display: "grid", gap: 8 }}>
            <div className="skeletonLine" />
            <div className="skeletonLine" />
            <div className="skeletonLine" />
          </div>
        ) : (
          <pre style={{ whiteSpace: "pre-wrap", margin: 0, maxHeight: "60vh", overflow: "auto" }}>
            {selectedLogs
              .map(
                (log) =>
                  `[${new Date(log.created_at).toLocaleTimeString()}] ${log.stage ?? "general"}: ${log.message ?? ""}`,
              )
              .join("\n") || "Sin logs disponibles."}
          </pre>
        )}
      </Modal>
    </section>
  );
}
