import type { CSSProperties } from "react";
import { useCallback, useEffect, useId, useState } from "react";

import { scenariosApi } from "@/features/scenarios/api/scenariosApi";
import type { OsemosysParamAuditPage } from "@/features/scenarios/api/scenariosApi";
import { Button } from "@/shared/components/Button";
import type { CsvSimulationResult, RunResult } from "@/types/domain";

const DIAGNOSTIC_PREVIEW_LIMIT = 10;
const PARAM_AUDIT_LIMIT = 15;

type DiagnosticsResult = Pick<RunResult | CsvSimulationResult, "infeasibility_diagnostics">;

/** Estado del registro de parámetros OSeMOSYS modificados en el escenario (no implica causalidad). */
export type ScenarioParamsForDiagnostics =
  | { state: "none" }
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "loaded"; names: string[] };

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

/** Región, variable (tecnología / combustible / emisión / UDC) y año desde `dimensions_json` de auditoría. */
function parseAuditDimensions(dim: Record<string, unknown> | null | undefined): {
  region: string;
  variable: string;
  year: string;
} {
  if (!dim || typeof dim !== "object") {
    return { region: "—", variable: "—", year: "—" };
  }
  const s = (v: unknown) => (v != null && String(v).trim() !== "" ? String(v).trim() : null);
  const region = s(dim.region_name) ?? "—";
  const year = s(dim.year) ?? "—";
  const tech = s(dim.technology_name);
  const fuel = s(dim.fuel_name);
  const emission = s(dim.emission_name);
  const udc = s(dim.udc_name);
  const parts: string[] = [];
  if (tech) parts.push(tech);
  if (fuel) parts.push(`Combustible: ${fuel}`);
  if (emission) parts.push(`Emisión: ${emission}`);
  if (udc) parts.push(`UDC: ${udc}`);
  const variable = parts.length ? parts.join(" · ") : "—";
  return { region, variable, year };
}

/** Texto legible para auditoría: compat. con filas antiguas `user:…` y orígenes `system:…`. */
function formatAuditActor(changedBy: string): string {
  if (changedBy.startsWith("user:")) {
    return changedBy.slice(5);
  }
  if (changedBy === "system:excel_apply") {
    return "Importación Excel (sistema)";
  }
  if (changedBy.startsWith("system:")) {
    const rest = changedBy.slice(7);
    return rest ? rest.replace(/_/g, " ") : "Sistema";
  }
  return changedBy;
}

function ScenarioParamDetails({ scenarioId, paramName }: { scenarioId: number; paramName: string }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [audit, setAudit] = useState<OsemosysParamAuditPage | null>(null);
  const [auditOffset, setAuditOffset] = useState(0);

  useEffect(() => {
    setAuditOffset(0);
  }, [paramName]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const a = await scenariosApi.listOsemosysParamAudit(scenarioId, paramName, {
        offset: auditOffset,
        limit: PARAM_AUDIT_LIMIT,
      });
      setAudit(a);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al cargar detalle del parámetro");
      setAudit(null);
    } finally {
      setLoading(false);
    }
  }, [scenarioId, paramName, auditOffset]);

  useEffect(() => {
    if (!open) return;
    void load();
  }, [open, load]);

  const auditTotalPages = Math.max(1, Math.ceil((audit?.total ?? 0) / PARAM_AUDIT_LIMIT));
  const auditPage = Math.floor(auditOffset / PARAM_AUDIT_LIMIT) + 1;

  return (
    <details
      style={{
        border: "1px solid rgba(255,255,255,0.12)",
        borderRadius: 8,
        padding: "6px 10px",
        background: "rgba(0,0,0,0.15)",
      }}
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
    >
      <summary style={{ cursor: "pointer", fontWeight: 600, listStylePosition: "outside" }}>{paramName}</summary>
      {open ? (
        <div style={{ display: "grid", gap: 12, marginTop: 10, paddingLeft: 4 }}>
          <small style={{ opacity: 0.78 }}>
            El historial solo incluye cambios registrados después de activar la auditoría en el sistema.
          </small>
          {loading ? <small style={{ opacity: 0.82 }}>Cargando…</small> : null}
          {error ? (
            <small style={{ opacity: 0.9, color: "rgba(252,165,165,0.95)" }}>{error}</small>
          ) : null}
          {!loading && !error ? (
            <>
              <div style={{ display: "grid", gap: 6 }}>
                <strong style={{ fontSize: 12 }}>Historial de cambios</strong>
                {audit && audit.items.length ? (
                  <>
                    <TablePagination
                      page={auditPage}
                      totalPages={auditTotalPages}
                      onPrevious={() => setAuditOffset((o) => Math.max(0, o - PARAM_AUDIT_LIMIT))}
                      onNext={() => {
                        const t = audit?.total ?? 0;
                        setAuditOffset((o) => (o + PARAM_AUDIT_LIMIT < t ? o + PARAM_AUDIT_LIMIT : o));
                      }}
                    />
                    <div style={{ overflowX: "auto" }}>
                      <table
                        style={{
                          width: "100%",
                          borderCollapse: "collapse",
                          fontSize: 12,
                          tableLayout: "fixed",
                        }}
                      >
                        <colgroup>
                          <col style={{ width: "22%" }} />
                          <col style={{ width: "8%" }} />
                          <col style={{ width: "14%" }} />
                          <col style={{ width: "12%" }} />
                          <col style={{ width: "12%" }} />
                          <col style={{ width: "14%" }} />
                          <col style={{ width: "18%" }} />
                        </colgroup>
                        <thead>
                          <tr>
                            <th style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.15)" }}>
                              Variable
                            </th>
                            <th style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.15)" }}>
                              Año
                            </th>
                            <th style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.15)" }}>
                              Región
                            </th>
                            <th style={{ textAlign: "right", padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.15)" }}>
                              Valor anterior
                            </th>
                            <th style={{ textAlign: "right", padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.15)" }}>
                              Nuevo valor
                            </th>
                            <th style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.15)" }}>
                              Usuario
                            </th>
                            <th style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.15)" }}>
                              Fecha
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {audit.items.map((row) => {
                            const d = parseAuditDimensions(row.dimensions_json as Record<string, unknown>);
                            return (
                              <tr key={row.id}>
                                <td
                                  style={{
                                    padding: "6px 8px",
                                    borderBottom: "1px solid rgba(255,255,255,0.06)",
                                    wordBreak: "break-word",
                                    verticalAlign: "top",
                                  }}
                                >
                                  {d.variable}
                                </td>
                                <td
                                  style={{
                                    padding: "6px 8px",
                                    borderBottom: "1px solid rgba(255,255,255,0.06)",
                                    whiteSpace: "nowrap",
                                    verticalAlign: "top",
                                  }}
                                >
                                  {d.year}
                                </td>
                                <td
                                  style={{
                                    padding: "6px 8px",
                                    borderBottom: "1px solid rgba(255,255,255,0.06)",
                                    wordBreak: "break-word",
                                    verticalAlign: "top",
                                  }}
                                >
                                  {d.region}
                                </td>
                                <td
                                  style={{
                                    padding: "6px 8px",
                                    borderBottom: "1px solid rgba(255,255,255,0.06)",
                                    textAlign: "right",
                                    whiteSpace: "nowrap",
                                    verticalAlign: "top",
                                  }}
                                >
                                  {row.old_value != null ? row.old_value.toLocaleString() : "—"}
                                </td>
                                <td
                                  style={{
                                    padding: "6px 8px",
                                    borderBottom: "1px solid rgba(255,255,255,0.06)",
                                    textAlign: "right",
                                    whiteSpace: "nowrap",
                                    verticalAlign: "top",
                                  }}
                                >
                                  {row.new_value != null ? row.new_value.toLocaleString() : "—"}
                                </td>
                                <td
                                  style={{
                                    padding: "6px 8px",
                                    borderBottom: "1px solid rgba(255,255,255,0.06)",
                                    fontSize: 11,
                                    wordBreak: "break-word",
                                    verticalAlign: "top",
                                  }}
                                >
                                  {formatAuditActor(row.changed_by)}
                                </td>
                                <td
                                  style={{
                                    padding: "6px 8px",
                                    borderBottom: "1px solid rgba(255,255,255,0.06)",
                                    whiteSpace: "nowrap",
                                    verticalAlign: "top",
                                  }}
                                >
                                  {new Date(row.created_at).toLocaleString()}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : (
                  <small style={{ opacity: 0.78 }}>Sin eventos de auditoría para este parámetro.</small>
                )}
              </div>
            </>
          ) : null}
        </div>
      ) : null}
    </details>
  );
}

type TabId = "constraints" | "scenarioParams";

export function InfeasibilityDiagnosticsPanel({
  result,
  scenarioParams = { state: "none" },
  scenarioId = null,
}: {
  result: DiagnosticsResult;
  scenarioParams?: ScenarioParamsForDiagnostics;
  /** Escenario asociado a la corrida; necesario para el historial por parámetro. */
  scenarioId?: number | null;
}) {
  const diagnostics = result.infeasibility_diagnostics;
  const baseId = useId();
  const tabConstraintsId = `${baseId}-tab-constraints`;
  const tabScenarioParamsId = `${baseId}-tab-scenario-params`;
  const panelConstraintsId = `${baseId}-panel-constraints`;
  const panelScenarioParamsId = `${baseId}-panel-scenario-params`;

  const [activeTab, setActiveTab] = useState<TabId>("constraints");
  const [constraintPage, setConstraintPage] = useState(1);

  const constraintCount = diagnostics?.constraint_violations.length ?? 0;
  const constraintTotalPages = Math.max(1, Math.ceil(constraintCount / DIAGNOSTIC_PREVIEW_LIMIT));
  const clampedConstraintPage = Math.max(1, Math.min(constraintPage, constraintTotalPages));

  if (!diagnostics) return null;

  const constraintStart = (clampedConstraintPage - 1) * DIAGNOSTIC_PREVIEW_LIMIT;
  const constraintViolations = diagnostics.constraint_violations.slice(
    constraintStart,
    constraintStart + DIAGNOSTIC_PREVIEW_LIMIT,
  );

  const tabBtnStyle = (active: boolean): CSSProperties => ({
    padding: "8px 14px",
    borderRadius: 8,
    border: "1px solid rgba(255,255,255,0.15)",
    background: active ? "rgba(239,68,68,0.25)" : "rgba(255,255,255,0.04)",
    color: "inherit",
    cursor: "pointer",
    fontWeight: active ? 600 : 500,
    fontSize: 13,
  });

  const hasConstraintViolations = constraintCount > 0;

  return (
    <section
      style={{
        border: "1px solid rgba(239,68,68,0.35)",
        borderRadius: 12,
        padding: 14,
        display: "grid",
        gap: 12,
        background: "rgba(127,29,29,0.12)",
      }}
    >
      <div style={{ display: "grid", gap: 4 }}>
        <h3 style={{ margin: 0 }}>Diagnóstico de infactibilidad</h3>
        <small style={{ opacity: 0.82 }}>
          Usa las pestañas para revisar las restricciones violadas o el registro de parámetros modificados en el escenario
          (cuando aplique).
        </small>
      </div>

      <div role="tablist" aria-label="Secciones del diagnóstico" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button
          type="button"
          role="tab"
          id={tabConstraintsId}
          aria-selected={activeTab === "constraints"}
          aria-controls={panelConstraintsId}
          tabIndex={activeTab === "constraints" ? 0 : -1}
          style={tabBtnStyle(activeTab === "constraints")}
          onClick={() => setActiveTab("constraints")}
        >
          Restricciones violadas
        </button>
        <button
          type="button"
          role="tab"
          id={tabScenarioParamsId}
          aria-selected={activeTab === "scenarioParams"}
          aria-controls={panelScenarioParamsId}
          tabIndex={activeTab === "scenarioParams" ? 0 : -1}
          style={tabBtnStyle(activeTab === "scenarioParams")}
          onClick={() => setActiveTab("scenarioParams")}
        >
          Parámetros del escenario
        </button>
      </div>

      {activeTab === "constraints" ? (
        <div
          role="tabpanel"
          id={panelConstraintsId}
          aria-labelledby={tabConstraintsId}
          style={{ display: "grid", gap: 8 }}
        >
          {constraintViolations.length ? (
            <>
              <small style={{ opacity: 0.78 }}>
                Mostrando {constraintStart + 1} a {constraintStart + constraintViolations.length} de {constraintCount}{" "}
                filas.
              </small>
              <TablePagination
                page={clampedConstraintPage}
                totalPages={constraintTotalPages}
                onPrevious={() =>
                  setConstraintPage((current) => Math.max(1, Math.min(current, constraintTotalPages) - 1))
                }
                onNext={() =>
                  setConstraintPage((current) =>
                    Math.min(constraintTotalPages, Math.max(1, Math.min(current, constraintTotalPages)) + 1),
                  )
                }
              />
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.2)" }}>
                        Restricción del modelo
                      </th>
                      <th
                        style={{ textAlign: "right", padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.2)" }}
                      >
                        Valor de la expresión
                      </th>
                      <th
                        style={{ textAlign: "right", padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.2)" }}
                      >
                        Cota inferior
                      </th>
                      <th
                        style={{ textAlign: "right", padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.2)" }}
                      >
                        Cota superior
                      </th>
                      <th
                        style={{ textAlign: "center", padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.2)" }}
                      >
                        Límite violado
                      </th>
                      <th
                        style={{ textAlign: "right", padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.2)" }}
                      >
                        Magnitud del incumplimiento
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {constraintViolations.map((item) => (
                      <tr key={`${item.name}-${item.side}`}>
                        <td
                          style={{
                            padding: "6px 8px",
                            borderBottom: "1px solid rgba(255,255,255,0.08)",
                            maxWidth: 360,
                            whiteSpace: "normal",
                            wordBreak: "break-word",
                          }}
                        >
                          {item.name}
                        </td>
                        <td
                          style={{
                            padding: "6px 8px",
                            textAlign: "right",
                            borderBottom: "1px solid rgba(255,255,255,0.08)",
                          }}
                        >
                          {item.body.toExponential(3)}
                        </td>
                        <td
                          style={{
                            padding: "6px 8px",
                            textAlign: "right",
                            borderBottom: "1px solid rgba(255,255,255,0.08)",
                          }}
                        >
                          {item.lower === null ? "—" : item.lower.toExponential(3)}
                        </td>
                        <td
                          style={{
                            padding: "6px 8px",
                            textAlign: "right",
                            borderBottom: "1px solid rgba(255,255,255,0.08)",
                          }}
                        >
                          {item.upper === null ? "—" : item.upper.toExponential(3)}
                        </td>
                        <td
                          style={{
                            padding: "6px 8px",
                            textAlign: "center",
                            borderBottom: "1px solid rgba(255,255,255,0.08)",
                          }}
                        >
                          {item.side === "UB" ? "Superior (UB)" : item.side === "LB" ? "Inferior (LB)" : item.side}
                        </td>
                        <td
                          style={{
                            padding: "6px 8px",
                            textAlign: "right",
                            borderBottom: "1px solid rgba(255,255,255,0.08)",
                          }}
                        >
                          {item.violation.toExponential(3)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <small style={{ opacity: 0.82 }}>
              No hay filas de restricciones violadas en este diagnóstico.
            </small>
          )}
        </div>
      ) : null}

      {activeTab === "scenarioParams" ? (
        <div
          role="tabpanel"
          id={panelScenarioParamsId}
          aria-labelledby={tabScenarioParamsId}
          style={{ display: "grid", gap: 8 }}
        >
          <strong>Parámetros modificados (registro del escenario)</strong>
          <small style={{ opacity: 0.78 }}>
            Lista de parámetros OSeMOSYS con cambios guardados en este escenario.{" "}
            <strong>No implica</strong> que alguno de ellos sea la causa única de la infactibilidad; solo sirve como
            referencia para contrastar con las restricciones violadas. Despliega un parámetro para ver el historial de
            cambios.
          </small>
          {scenarioParams.state === "none" ? (
            <small style={{ opacity: 0.82 }}>
              Esta corrida no está asociada a un escenario persistido en la aplicación (por ejemplo, simulación solo
              desde CSV), o no hay datos de registro de parámetros.
            </small>
          ) : null}
          {scenarioParams.state === "loading" ? (
            <small style={{ opacity: 0.82 }}>Cargando registro del escenario…</small>
          ) : null}
          {scenarioParams.state === "error" ? (
            <small style={{ opacity: 0.82, color: "rgba(252,165,165,0.95)" }}>
              No se pudo cargar el escenario: {scenarioParams.message}
            </small>
          ) : null}
          {scenarioParams.state === "loaded" && scenarioParams.names.length === 0 ? (
            <small style={{ opacity: 0.82 }}>
              No hay parámetros modificados registrados para este escenario (o el escenario no tiene historial de ediciones
              en la app).
            </small>
          ) : null}
          {scenarioParams.state === "loaded" && scenarioParams.names.length > 0 ? (
            <div style={{ display: "grid", gap: 8 }}>
              {scenarioId != null ? (
                scenarioParams.names.map((name) => (
                  <ScenarioParamDetails key={name} scenarioId={scenarioId} paramName={name} />
                ))
              ) : (
                <ul
                  style={{
                    margin: 0,
                    paddingLeft: 20,
                    display: "grid",
                    gap: 6,
                    fontSize: 13,
                  }}
                >
                  {scenarioParams.names.map((name) => (
                    <li key={name}>{name}</li>
                  ))}
                </ul>
              )}
            </div>
          ) : null}
        </div>
      ) : null}

      {!hasConstraintViolations &&
      scenarioParams.state !== "loading" &&
      !(scenarioParams.state === "loaded" && scenarioParams.names.length > 0) ? (
        <small style={{ opacity: 0.82 }}>No se reportaron violaciones explícitas en el diagnóstico.</small>
      ) : null}
    </section>
  );
}
