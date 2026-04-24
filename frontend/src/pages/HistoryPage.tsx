/**
 * Historial — página con pestañas agrupando distintos tipos de auditoría.
 *
 * Por ahora la única pestaña es "Eliminaciones" (bitácora de escenarios y
 * simulaciones borrados). La estructura está preparada para sumar otras
 * pestañas más adelante (ej. cambios en catálogos, cambios en valores
 * OSeMOSYS, accesos, etc.).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { deletionLogApi } from "@/features/deletion-log/api/deletionLogApi";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { DataTable } from "@/shared/components/DataTable";
import type { DeletionLogEntry } from "@/types/domain";
import {
  catalogMetaAuditApi,
  type AuditEntry,
} from "@/features/catalogMeta/api/catalogMetaApi";

type HistoryTab = "deletions" | "catalog_meta";

export function HistoryPage() {
  const [activeTab, setActiveTab] = useState<HistoryTab>("deletions");

  return (
    <section className="pageSection" style={{ display: "grid", gap: 12 }}>
      <div>
        <h1 style={{ margin: 0 }}>Historial</h1>
        <p style={{ margin: "6px 0 0", opacity: 0.75 }}>
          Bitácoras de auditoría del sistema. Cada pestaña agrupa un tipo de
          evento para facilitar gobernanza y trazabilidad.
        </p>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <Button
          variant={activeTab === "deletions" ? "primary" : "ghost"}
          onClick={() => setActiveTab("deletions")}
        >
          Eliminaciones
        </Button>
        <Button
          variant={activeTab === "catalog_meta" ? "primary" : "ghost"}
          onClick={() => setActiveTab("catalog_meta")}
        >
          Catálogo de visualización
        </Button>
      </div>

      {activeTab === "deletions" ? <DeletionsTab /> : null}
      {activeTab === "catalog_meta" ? <CatalogMetaAuditTab /> : null}
    </section>
  );
}

// ─── Pestaña: Eliminaciones ────────────────────────────────────────────────

function DeletionsTab() {
  const [rows, setRows] = useState<DeletionLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const fetchRows = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await deletionLogApi.list({ cantidad: 200, offset: 1 });
      setRows(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cargar el historial.");
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchRows();
  }, [fetchRows]);

  const stats = useMemo(() => {
    const scenarios = rows.filter((r) => r.entity_type === "SCENARIO").length;
    const jobs = rows.filter((r) => r.entity_type === "SIMULATION_JOB").length;
    return { scenarios, jobs, total: rows.length };
  }, [rows]);

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <p style={{ margin: 0, opacity: 0.78, maxWidth: 680 }}>
          Qué se ha borrado, por quién y cuándo. El registro es inmutable: se
          crea automáticamente con cada delete de escenario o simulación y el
          borrado es permanente (la fila original no se puede recuperar, pero
          aquí queda el snapshot de sus campos clave).
        </p>
        <Button variant="ghost" onClick={() => void fetchRows()} disabled={loading}>
          {loading ? "Cargando..." : "Refrescar"}
        </Button>
      </div>

      <div
        style={{
          display: "grid",
          gap: 10,
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
        }}
      >
        {[
          { label: "Total eliminaciones", value: stats.total },
          { label: "Escenarios", value: stats.scenarios },
          { label: "Simulaciones", value: stats.jobs },
        ].map((item) => (
          <div
            key={item.label}
            style={{
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: 12,
              padding: 14,
            }}
          >
            <div style={{ fontSize: 12, opacity: 0.7 }}>{item.label}</div>
            <div style={{ fontSize: 24, fontWeight: 700 }}>{item.value}</div>
          </div>
        ))}
      </div>

      {error ? (
        <div style={{ border: "1px solid rgba(239,68,68,0.4)", borderRadius: 12, padding: 12 }}>
          <strong>Error cargando historial</strong>
          <p style={{ marginBottom: 0 }}>{error}</p>
        </div>
      ) : null}

      <DataTable
        rows={rows}
        rowKey={(r) => String(r.id)}
        columns={[
          {
            key: "entity_type",
            header: "Tipo",
            render: (r) => (
              <Badge variant={r.entity_type === "SCENARIO" ? "info" : "neutral"}>
                {r.entity_type === "SCENARIO" ? "Escenario" : "Simulación"}
              </Badge>
            ),
            filter: {
              type: "multiselect",
              getValue: (r) => r.entity_type,
              getLabel: (v) =>
                v === "SCENARIO" ? "Escenario" : v === "SIMULATION_JOB" ? "Simulación" : v,
              options: [
                { value: "SCENARIO", label: "Escenario" },
                { value: "SIMULATION_JOB", label: "Simulación" },
              ],
            },
          },
          {
            key: "entity_id",
            header: "ID original",
            render: (r) => (
              <span style={{ fontFamily: "monospace", opacity: 0.75 }}>#{r.entity_id}</span>
            ),
            filter: {
              type: "text",
              getValue: (r) => String(r.entity_id),
              placeholder: "#id",
            },
          },
          {
            key: "entity_name",
            header: "Nombre",
            render: (r) => r.entity_name,
            filter: {
              type: "text",
              getValue: (r) => r.entity_name,
              placeholder: "Nombre…",
            },
          },
          {
            key: "deleted_by",
            header: "Borrado por",
            render: (r) => r.deleted_by_username,
            filter: {
              type: "multiselect",
              getValue: (r) => r.deleted_by_username,
              placeholder: "Usuario…",
            },
          },
          {
            key: "deleted_at",
            header: "Fecha",
            render: (r) => new Date(r.deleted_at).toLocaleString(),
          },
          {
            key: "details",
            header: "Detalle",
            render: (r) =>
              r.details_json ? (
                <button
                  type="button"
                  className="btn btn--ghost"
                  style={{ fontSize: 12, padding: "4px 8px" }}
                  onClick={() => setExpandedId((prev) => (prev === r.id ? null : r.id))}
                >
                  {expandedId === r.id ? "Ocultar" : "Ver JSON"}
                </button>
              ) : (
                <span style={{ opacity: 0.6 }}>—</span>
              ),
          },
        ]}
        searchableText={(r) =>
          `${r.entity_type} ${r.entity_id} ${r.entity_name} ${r.deleted_by_username}`
        }
      />

      {expandedId != null && rows.find((r) => r.id === expandedId)?.details_json ? (
        <div
          style={{
            border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: 12,
            padding: 12,
            background: "rgba(15,23,42,0.5)",
          }}
        >
          <strong style={{ fontSize: 13 }}>
            Snapshot de la fila eliminada (#{expandedId})
          </strong>
          <pre
            style={{
              marginTop: 8,
              marginBottom: 0,
              fontSize: 12,
              overflowX: "auto",
              color: "rgba(224,233,244,0.9)",
            }}
          >
            {JSON.stringify(rows.find((r) => r.id === expandedId)?.details_json, null, 2)}
          </pre>
        </div>
      ) : null}
    </div>
  );
}

// ─── Pestaña: Catálogo de visualización ────────────────────────────────────

const PAGE_SIZES = [25, 50, 100, 200] as const;

const TABLE_LABELS: Record<string, string> = {
  catalog_meta_color_palette: "Colores",
  catalog_meta_label: "Etiquetas",
  catalog_meta_sector_mapping: "Sectores",
  catalog_meta_tech_family: "Familias tech",
  catalog_meta_chart_module: "Módulos",
  catalog_meta_chart_submodule: "Submódulos",
  catalog_meta_chart_config: "Gráficas",
  catalog_meta_chart_subfilter: "Sub-filtros",
  catalog_meta_chart_subfilter_group: "Grupos sub-filtro",
  catalog_meta_variable_unit: "Unidades",
};

const ACTION_LABELS: Record<string, string> = {
  INSERT: "Crear",
  UPDATE: "Actualizar",
  DELETE: "Eliminar",
};

function CatalogMetaAuditTab() {
  const [rows, setRows] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [tables, setTables] = useState<string[]>([]);
  const [table, setTable] = useState<string>("");
  const [action, setAction] = useState<string>("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(50);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Parameters<typeof catalogMetaAuditApi.list>[0] = {
        offset: (page - 1) * pageSize,
        limit: pageSize,
      };
      if (table) params.table_name = table;
      if (action) params.action = action;
      const resp = await catalogMetaAuditApi.list(params);
      setRows(resp.items);
      setTotal(resp.total);
      setTables(resp.tables);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error cargando historial");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, table, action]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / pageSize)),
    [total, pageSize],
  );

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div
        style={{
          display: "flex",
          gap: 10,
          alignItems: "center",
          flexWrap: "wrap",
          justifyContent: "space-between",
        }}
      >
        <p style={{ margin: 0, opacity: 0.78, maxWidth: 680 }}>
          Historial de cambios en el catálogo editable de visualización: colores,
          etiquetas, módulos, gráficas, sub-filtros. Cada fila registra qué
          tabla, qué fila, qué cambio y quién lo hizo.
        </p>
        <Button variant="ghost" onClick={() => void reload()} disabled={loading}>
          {loading ? "Cargando..." : "Refrescar"}
        </Button>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <label style={{ fontSize: 13, display: "inline-flex", alignItems: "center", gap: 6 }}>
          Tabla:
          <select
            value={table}
            onChange={(e) => {
              setTable(e.target.value);
              setPage(1);
            }}
            style={auditFieldStyle}
          >
            <option value="">(todas)</option>
            {tables.map((t) => (
              <option key={t} value={t}>
                {TABLE_LABELS[t] ?? t}
              </option>
            ))}
          </select>
        </label>
        <label style={{ fontSize: 13, display: "inline-flex", alignItems: "center", gap: 6 }}>
          Acción:
          <select
            value={action}
            onChange={(e) => {
              setAction(e.target.value);
              setPage(1);
            }}
            style={auditFieldStyle}
          >
            <option value="">(todas)</option>
            <option value="INSERT">Crear</option>
            <option value="UPDATE">Actualizar</option>
            <option value="DELETE">Eliminar</option>
          </select>
        </label>
        <div style={{ flex: 1 }} />
        <small style={{ opacity: 0.75 }}>
          {total.toLocaleString("es-CO")} {total === 1 ? "cambio" : "cambios"}
        </small>
      </div>

      {error ? (
        <div
          role="alert"
          style={{
            padding: "8px 12px",
            background: "rgba(255,90,90,0.08)",
            border: "1px solid rgba(255,90,90,0.3)",
            borderRadius: 6,
            fontSize: 13,
            color: "rgba(255,180,180,0.95)",
          }}
        >
          {error}
        </div>
      ) : null}

      <div style={{ border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead style={{ background: "rgba(255,255,255,0.03)" }}>
            <tr>
              <AuditTh style={{ width: 170 }}>Fecha</AuditTh>
              <AuditTh style={{ width: 140 }}>Tabla</AuditTh>
              <AuditTh style={{ width: 70 }}>ID</AuditTh>
              <AuditTh style={{ width: 100 }}>Acción</AuditTh>
              <AuditTh style={{ width: 140 }}>Usuario</AuditTh>
              <AuditTh>Cambios</AuditTh>
            </tr>
          </thead>
          <tbody>
            {loading && rows.length === 0 ? (
              <tr>
                <AuditTd colSpan={6} style={{ padding: 18, opacity: 0.7 }}>
                  Cargando…
                </AuditTd>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <AuditTd colSpan={6} style={{ padding: 18, opacity: 0.7 }}>
                  Sin cambios registrados.
                </AuditTd>
              </tr>
            ) : (
              rows.map((r) => {
                const expanded = expandedId === r.id;
                return (
                  <>
                    <tr key={r.id} style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}>
                      <AuditTd>
                        <small>{new Date(r.changed_at).toLocaleString()}</small>
                      </AuditTd>
                      <AuditTd>{TABLE_LABELS[r.table_name] ?? r.table_name}</AuditTd>
                      <AuditTd>
                        <code style={{ fontSize: 12, opacity: 0.8 }}>
                          {r.row_id ?? "—"}
                        </code>
                      </AuditTd>
                      <AuditTd>
                        <Badge
                          variant={
                            r.action === "INSERT"
                              ? "info"
                              : r.action === "DELETE"
                                ? "danger"
                                : "neutral"
                          }
                        >
                          {ACTION_LABELS[r.action] ?? r.action}
                        </Badge>
                      </AuditTd>
                      <AuditTd>{r.changed_by_username ?? "—"}</AuditTd>
                      <AuditTd>
                        <ChangeSummary diff={r.diff_json} />
                        {r.diff_json ? (
                          <button
                            type="button"
                            className="btn btn--ghost"
                            style={{ fontSize: 11, padding: "2px 6px", marginLeft: 6 }}
                            onClick={() => setExpandedId(expanded ? null : r.id)}
                          >
                            {expanded ? "Ocultar" : "Ver JSON"}
                          </button>
                        ) : null}
                      </AuditTd>
                    </tr>
                    {expanded && r.diff_json ? (
                      <tr>
                        <AuditTd colSpan={6} style={{ background: "rgba(15,23,42,0.4)", padding: 10 }}>
                          <pre style={{ margin: 0, fontSize: 11, overflowX: "auto" }}>
                            {JSON.stringify(r.diff_json, null, 2)}
                          </pre>
                        </AuditTd>
                      </tr>
                    ) : null}
                  </>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <div
        style={{
          display: "flex",
          gap: 10,
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
        }}
      >
        <small style={{ opacity: 0.75 }}>
          Página {page} de {totalPages}
        </small>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <label style={{ fontSize: 12 }}>
            Por página:
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              style={{ ...auditFieldStyle, marginLeft: 6 }}
            >
              {PAGE_SIZES.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <Button variant="ghost" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1 || loading}>
            ←
          </Button>
          <Button variant="ghost" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages || loading}>
            →
          </Button>
        </div>
      </div>
    </div>
  );
}

function ChangeSummary({ diff }: { diff: AuditEntry["diff_json"] }) {
  if (!diff || typeof diff !== "object" || Array.isArray(diff)) {
    return <span style={{ opacity: 0.6 }}>—</span>;
  }
  const d = diff as { before?: Record<string, unknown>; after?: Record<string, unknown> };
  const keys = new Set<string>([...Object.keys(d.before ?? {}), ...Object.keys(d.after ?? {})]);
  if (keys.size === 0) return <span style={{ opacity: 0.6 }}>—</span>;
  return (
    <span style={{ fontSize: 12, opacity: 0.9 }}>
      {Array.from(keys).slice(0, 3).map((k) => (
        <span key={k} style={{ marginRight: 10 }}>
          <b>{k}</b>:{" "}
          {d.before?.[k] !== undefined ? (
            <>
              <s style={{ opacity: 0.55 }}>{fmt(d.before[k])}</s>{" → "}
            </>
          ) : null}
          {fmt(d.after?.[k])}
        </span>
      ))}
      {keys.size > 3 ? <small style={{ opacity: 0.5 }}>(+{keys.size - 3} más)</small> : null}
    </span>
  );
}

function fmt(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string") return v;
  return JSON.stringify(v);
}

function AuditTh({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <th
      style={{
        textAlign: "left",
        fontSize: 12,
        padding: "8px 10px",
        color: "var(--muted)",
        fontWeight: 500,
        ...style,
      }}
    >
      {children}
    </th>
  );
}

function AuditTd({ children, style, colSpan }: { children: React.ReactNode; style?: React.CSSProperties; colSpan?: number }) {
  return (
    <td style={{ padding: "6px 10px", fontSize: 13, ...style }} colSpan={colSpan}>
      {children}
    </td>
  );
}

const auditFieldStyle: React.CSSProperties = {
  background: "transparent",
  color: "inherit",
  border: "1px solid rgba(255,255,255,0.12)",
  borderRadius: 4,
  padding: "3px 8px",
  fontSize: 13,
};
