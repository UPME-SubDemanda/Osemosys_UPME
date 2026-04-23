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

type HistoryTab = "deletions";

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
      </div>

      {activeTab === "deletions" ? <DeletionsTab /> : null}
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
