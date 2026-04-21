/**
 * ScenarioParamsTab — pestaña de "Parámetros del escenario" para el reporte de
 * infactibilidad. Muestra los parámetros OSeMOSYS modificados en el escenario
 * con su historial de auditoría paginado. Acepta `iisParamNames` (Set) para
 * marcar con badge los parámetros que también aparecen en el IIS (sospechosos
 * de alto impacto — cambios del escenario que tocan restricciones del IIS).
 *
 * Extraído desde InfeasibilityDiagnosticsPanel.tsx para reutilizarse en la
 * página unificada InfeasibilityReportPage.
 */
import { useCallback, useEffect, useState } from "react";

import { scenariosApi } from "@/features/scenarios/api/scenariosApi";
import type { OsemosysParamAuditPage } from "@/features/scenarios/api/scenariosApi";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";

const PARAM_AUDIT_LIMIT = 15;

/** Estado del registro de parámetros OSeMOSYS modificados en el escenario. */
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

function formatAuditActor(changedBy: string): string {
  if (changedBy.startsWith("user:")) return changedBy.slice(5);
  if (changedBy === "system:excel_apply") return "Importación Excel (sistema)";
  if (changedBy.startsWith("system:")) {
    const rest = changedBy.slice(7);
    return rest ? rest.replace(/_/g, " ") : "Sistema";
  }
  return changedBy;
}

function ScenarioParamDetails({
  scenarioId,
  paramName,
  inIIS,
}: {
  scenarioId: number;
  paramName: string;
  inIIS: boolean;
}) {
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
        border: inIIS ? "1px solid rgba(239,68,68,0.5)" : "1px solid rgba(255,255,255,0.12)",
        borderRadius: 8,
        padding: "6px 10px",
        background: inIIS ? "rgba(127,29,29,0.18)" : "rgba(0,0,0,0.15)",
      }}
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
    >
      <summary style={{ cursor: "pointer", fontWeight: 600, listStylePosition: "outside", display: "flex", gap: 8, alignItems: "center" }}>
        <span>{paramName}</span>
        {inIIS ? (
          <span title="Este parámetro aparece en el IIS — es un sospechoso de alto impacto">
            <Badge variant="danger">En IIS</Badge>
          </span>
        ) : null}
      </summary>
      {open ? (
        <div style={{ display: "grid", gap: 12, marginTop: 10, paddingLeft: 4 }}>
          <small style={{ opacity: 0.78 }}>
            El historial solo incluye cambios registrados después de activar la auditoría en el sistema.
          </small>
          {loading ? <small style={{ opacity: 0.82 }}>Cargando…</small> : null}
          {error ? <small style={{ opacity: 0.9, color: "rgba(252,165,165,0.95)" }}>{error}</small> : null}
          {!loading && !error ? (
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
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, tableLayout: "fixed" }}>
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
                          <th style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.15)" }}>Variable</th>
                          <th style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.15)" }}>Año</th>
                          <th style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.15)" }}>Región</th>
                          <th style={{ textAlign: "right", padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.15)" }}>Valor anterior</th>
                          <th style={{ textAlign: "right", padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.15)" }}>Nuevo valor</th>
                          <th style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.15)" }}>Usuario</th>
                          <th style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.15)" }}>Fecha</th>
                        </tr>
                      </thead>
                      <tbody>
                        {audit.items.map((row) => {
                          const d = parseAuditDimensions(row.dimensions_json as Record<string, unknown>);
                          return (
                            <tr key={row.id}>
                              <td style={{ padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.06)", wordBreak: "break-word", verticalAlign: "top" }}>{d.variable}</td>
                              <td style={{ padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.06)", whiteSpace: "nowrap", verticalAlign: "top" }}>{d.year}</td>
                              <td style={{ padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.06)", wordBreak: "break-word", verticalAlign: "top" }}>{d.region}</td>
                              <td style={{ padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.06)", textAlign: "right", whiteSpace: "nowrap", verticalAlign: "top" }}>
                                {row.old_value != null ? row.old_value.toLocaleString() : "—"}
                              </td>
                              <td style={{ padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.06)", textAlign: "right", whiteSpace: "nowrap", verticalAlign: "top" }}>
                                {row.new_value != null ? row.new_value.toLocaleString() : "—"}
                              </td>
                              <td style={{ padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.06)", fontSize: 11, wordBreak: "break-word", verticalAlign: "top" }}>
                                {formatAuditActor(row.changed_by)}
                              </td>
                              <td style={{ padding: "6px 8px", borderBottom: "1px solid rgba(255,255,255,0.06)", whiteSpace: "nowrap", verticalAlign: "top" }}>
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
          ) : null}
        </div>
      ) : null}
    </details>
  );
}

export function ScenarioParamsTab({
  scenarioParams,
  scenarioId,
  iisParamNames,
}: {
  scenarioParams: ScenarioParamsForDiagnostics;
  scenarioId: number | null;
  iisParamNames: Set<string>;
}) {
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <small style={{ opacity: 0.78 }}>
        Lista de parámetros OSeMOSYS con cambios guardados en este escenario. Los marcados{" "}
        <Badge variant="danger">En IIS</Badge> también aparecen en el IIS de esta corrida —
        son los sospechosos más probables de haber causado la infactibilidad.
      </small>
      {scenarioParams.state === "none" ? (
        <small style={{ opacity: 0.82 }}>
          Esta corrida no está asociada a un escenario persistido en la aplicación (por ejemplo,
          simulación solo desde CSV), o no hay datos de registro de parámetros.
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
          No hay parámetros modificados registrados para este escenario (o el escenario no tiene
          historial de ediciones en la app).
        </small>
      ) : null}
      {scenarioParams.state === "loaded" && scenarioParams.names.length > 0 ? (
        <div style={{ display: "grid", gap: 8 }}>
          {scenarioId != null ? (
            [...scenarioParams.names]
              // Parámetros que están en el IIS primero (sospechosos de alto impacto).
              .sort((a, b) => {
                const inA = iisParamNames.has(a) ? 1 : 0;
                const inB = iisParamNames.has(b) ? 1 : 0;
                if (inA !== inB) return inB - inA;
                return a.localeCompare(b);
              })
              .map((name) => (
                <ScenarioParamDetails
                  key={name}
                  scenarioId={scenarioId}
                  paramName={name}
                  inIIS={iisParamNames.has(name)}
                />
              ))
          ) : (
            <small style={{ opacity: 0.82 }}>
              (No se puede cargar el historial: escenario sin ID asociado.)
            </small>
          )}
        </div>
      ) : null}
    </div>
  );
}
