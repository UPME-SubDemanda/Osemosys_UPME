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
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { DataTable } from "@/shared/components/DataTable";
import { Modal } from "@/shared/components/Modal";
import { TextField } from "@/shared/components/TextField";
import { paths } from "@/routes/paths";
import type {
  CsvSimulationResult,
  Scenario,
  SimulationLog,
  SimulationOverview,
  SimulationRun,
  SimulationSolver,
} from "@/types/domain";

const ACTIVE_STATUSES = new Set(["QUEUED", "RUNNING"]);

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
    setCsvResult(null);
    try {
      const result = await simulationApi.submitFromCsv(csvZipFile, csvSolverName);
      setCsvResult(result);
      const statusLower = result.solver_status.toLowerCase();
      push(
        statusLower.includes("optimal")
          ? "Simulación desde CSV completada."
          : `Simulación desde CSV finalizada con estado ${result.solver_status}.`,
        statusLower.includes("optimal") ? "success" : "info",
      );
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
            Sube un ZIP con CSV ya procesados (`YEAR.csv`, `REGION.csv`, `TECHNOLOGY.csv`, etc.) para ejecutar una corrida directa sin escenario en base de datos.
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
            {csvSubmitting ? "Ejecutando..." : "Ejecutar desde CSV"}
          </Button>
        </div>
        {csvZipFile ? (
          <small style={{ opacity: 0.78 }}>
            Archivo seleccionado: <strong>{csvZipFile.name}</strong>
          </small>
        ) : null}

        {csvResult ? (
          <div style={{ display: "grid", gap: 12 }}>
            <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
              <Badge
                variant={
                  csvResult.solver_status.toLowerCase().includes("optimal")
                    ? "success"
                    : csvResult.solver_status.toLowerCase().includes("infeasible")
                      ? "danger"
                      : "warning"
                }
              >
                {csvResult.solver_status}
              </Badge>
              <span>Solver: {csvResult.solver_name === "highs" ? "HiGHS" : "GLPK"}</span>
              <Button variant="ghost" onClick={downloadCsvResultJson}>
                Descargar JSON
              </Button>
            </div>

            <div
              style={{
                display: "grid",
                gap: 10,
                gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
              }}
            >
              {[
                { label: "Objetivo", value: csvResult.objective_value.toLocaleString() },
                { label: "Cobertura", value: `${(csvResult.coverage_ratio * 100).toFixed(2)}%` },
                { label: "Demanda total", value: csvResult.total_demand.toLocaleString() },
                { label: "Dispatch total", value: csvResult.total_dispatch.toLocaleString() },
                { label: "Unmet total", value: csvResult.total_unmet.toLocaleString() },
              ].map((item) => (
                <div key={item.label} style={{ border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, padding: 14 }}>
                  <div style={{ fontSize: 12, opacity: 0.7 }}>{item.label}</div>
                  <div style={{ fontSize: 20, fontWeight: 700 }}>{item.value}</div>
                </div>
              ))}
            </div>

            {csvResult.infeasibility_diagnostics ? (
              <div style={{ display: "grid", gap: 12 }}>
                <div style={{ border: "1px solid rgba(239,68,68,0.3)", borderRadius: 12, padding: 12, display: "grid", gap: 10 }}>
                  <h3 style={{ margin: 0 }}>Diagnóstico de infactibilidad</h3>
                  {csvResult.infeasibility_diagnostics.constraint_violations.length ? (
                    <div style={{ display: "grid", gap: 8 }}>
                      <strong>Restricciones violadas</strong>
                      <div style={{ overflow: "auto" }}>
                        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                          <thead>
                            <tr>
                              <th style={{ textAlign: "left", padding: "4px 8px", borderBottom: "1px solid rgba(255,255,255,0.2)" }}>Restricción</th>
                              <th style={{ textAlign: "right", padding: "4px 8px", borderBottom: "1px solid rgba(255,255,255,0.2)" }}>Body</th>
                              <th style={{ textAlign: "right", padding: "4px 8px", borderBottom: "1px solid rgba(255,255,255,0.2)" }}>Lower</th>
                              <th style={{ textAlign: "right", padding: "4px 8px", borderBottom: "1px solid rgba(255,255,255,0.2)" }}>Upper</th>
                              <th style={{ textAlign: "center", padding: "4px 8px", borderBottom: "1px solid rgba(255,255,255,0.2)" }}>Lado</th>
                              <th style={{ textAlign: "right", padding: "4px 8px", borderBottom: "1px solid rgba(255,255,255,0.2)" }}>Violación</th>
                            </tr>
                          </thead>
                          <tbody>
                            {csvResult.infeasibility_diagnostics.constraint_violations.slice(0, 10).map((item) => (
                              <tr key={`${item.name}-${item.side}`}>
                                <td style={{ padding: "4px 8px" }}>{item.name}</td>
                                <td style={{ padding: "4px 8px", textAlign: "right" }}>{item.body.toExponential(3)}</td>
                                <td style={{ padding: "4px 8px", textAlign: "right" }}>{item.lower === null ? "—" : item.lower.toExponential(3)}</td>
                                <td style={{ padding: "4px 8px", textAlign: "right" }}>{item.upper === null ? "—" : item.upper.toExponential(3)}</td>
                                <td style={{ padding: "4px 8px", textAlign: "center" }}>{item.side}</td>
                                <td style={{ padding: "4px 8px", textAlign: "right" }}>{item.violation.toExponential(3)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ) : null}

                  {csvResult.infeasibility_diagnostics.var_bound_conflicts.length ? (
                    <div style={{ display: "grid", gap: 8 }}>
                      <strong>Bounds conflictivos</strong>
                      <div style={{ overflow: "auto" }}>
                        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                          <thead>
                            <tr>
                              <th style={{ textAlign: "left", padding: "4px 8px", borderBottom: "1px solid rgba(255,255,255,0.2)" }}>Variable</th>
                              <th style={{ textAlign: "right", padding: "4px 8px", borderBottom: "1px solid rgba(255,255,255,0.2)" }}>LB</th>
                              <th style={{ textAlign: "right", padding: "4px 8px", borderBottom: "1px solid rgba(255,255,255,0.2)" }}>UB</th>
                              <th style={{ textAlign: "right", padding: "4px 8px", borderBottom: "1px solid rgba(255,255,255,0.2)" }}>Gap</th>
                            </tr>
                          </thead>
                          <tbody>
                            {csvResult.infeasibility_diagnostics.var_bound_conflicts.slice(0, 10).map((item) => (
                              <tr key={item.name}>
                                <td style={{ padding: "4px 8px" }}>{item.name}</td>
                                <td style={{ padding: "4px 8px", textAlign: "right" }}>{item.lb.toExponential(3)}</td>
                                <td style={{ padding: "4px 8px", textAlign: "right" }}>{item.ub.toExponential(3)}</td>
                                <td style={{ padding: "4px 8px", textAlign: "right" }}>{item.gap.toExponential(3)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>
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
            { key: "scenario", header: "Escenario", render: (r) => r.scenario_name ?? `#${r.scenario_id}` },
            { key: "user", header: "Usuario", render: (r) => r.username ?? r.user_id },
            {
              key: "solver",
              header: "Solver",
              render: (r) => (r.solver_name === "highs" ? "HiGHS" : "GLPK"),
            },
            {
              key: "status",
              header: "Estado",
              render: (r) => (
                <Badge
                  variant={
                    r.status === "SUCCEEDED"
                      ? "success"
                      : r.status === "FAILED" || r.status === "CANCELLED"
                        ? "danger"
                        : "warning"
                  }
                >
                  {r.status === "QUEUED"
                    ? "En cola"
                    : r.status === "RUNNING"
                      ? "En ejecución"
                      : r.status === "SUCCEEDED"
                        ? "Exitosa"
                        : r.status === "FAILED"
                          ? "Fallida"
                          : "Cancelada"}
                </Badge>
              ),
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
          searchableText={(r) => `${r.id} ${r.scenario_name ?? ""} ${r.username ?? ""} ${r.status} ${r.queue_position ?? ""}`}
        />
      </article>

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
