/**
 * ResultsPage - Lista de resultados de simulaciones
 *
 * Muestra jobs de simulación con filtros:
 * - Por estado (QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED)
 * - Por rango de fechas (desde/hasta)
 *
 * Endpoints usados:
 * - simulationApi.listRuns({ cantidad: 100 })
 * - scenariosApi.listScenarios() para mapear scenario_id a nombre
 *
 * Cada fila enlaza a ResultDetailPage para ver gráficas y datos.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { scenariosApi } from "@/features/scenarios/api/scenariosApi";
import { simulationApi } from "@/features/simulation/api/simulationApi";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { DataTable } from "@/shared/components/DataTable";
import { ScenarioTagChip } from "@/shared/components/ScenarioTagChip";
import { RunDisplayNameEditor } from "@/features/simulation/components/RunDisplayNameEditor";
import { getSimulationRunStatusDisplay } from "@/features/simulation/simulationRunStatus";
import { paths } from "@/routes/paths";
import type { Scenario, SimulationRun } from "@/types/domain";

export function ResultsPage() {
  const [runs, setRuns] = useState<SimulationRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<SimulationRun["status"] | "ALL">("ALL");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [scenarioMap, setScenarioMap] = useState<Record<number, Scenario>>({});

  /** Carga jobs y escenarios en paralelo para tener nombres de escenario */
  const fetchRuns = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [runsRes, scenariosRes] = await Promise.all([
        simulationApi.listRuns({ cantidad: 100, offset: 1 }),
        scenariosApi.listScenarios({ cantidad: 200 }),
      ]);
      setRuns(runsRes.data);
      setScenarioMap(Object.fromEntries(scenariosRes.data.map((s) => [s.id, s])));
    } catch (err: unknown) {
      setRuns([]);
      setError(err instanceof Error ? err.message : "No se pudieron cargar los jobs.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchRuns();
  }, [fetchRuns]);

  // Filtrado por estado y rango de fechas (queued_at)
  const filteredRuns = useMemo(() => {
    return runs.filter((run) => {
      if (statusFilter !== "ALL" && run.status !== statusFilter) return false;
      const created = new Date(run.queued_at).getTime();
      if (fromDate) {
        const from = new Date(`${fromDate}T00:00:00`).getTime();
        if (created < from) return false;
      }
      if (toDate) {
        const to = new Date(`${toDate}T23:59:59`).getTime();
        if (created > to) return false;
      }
      return true;
    });
  }, [fromDate, runs, statusFilter, toDate]);

  const handleRunDisplayNameSaved = useCallback((jobId: number, next: string | null) => {
    setRuns((prev) =>
      prev.map((r) => (r.id === jobId ? { ...r, display_name: next } : r)),
    );
  }, []);

  return (
    <section className="pageSection" style={{ display: "grid", gap: 12 }}>
      <div className="toolbarRow">
        <div>
          <h1 style={{ margin: 0 }}>Resultados</h1>
          <p style={{ margin: "6px 0 0", opacity: 0.75 }}>
            Filtra jobs y abre rápidamente el detalle del resultado.
          </p>
        </div>
        <Button variant="ghost" onClick={() => void fetchRuns()} disabled={loading}>
          {loading ? "Cargando..." : "Refrescar"}
        </Button>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))",
          gap: 10,
        }}
      >
        <label className="field">
          <span className="field__label">Estado</span>
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
        <label className="field">
          <span className="field__label">Desde</span>
          <input className="field__input" type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
        </label>
        <label className="field">
          <span className="field__label">Hasta</span>
          <input className="field__input" type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
        </label>
      </div>

      {loading ? (
        <div style={{ display: "grid", gap: 8 }}>
          <div className="skeletonLine" />
          <div className="skeletonLine" />
          <div className="skeletonLine" />
        </div>
      ) : null}
      {!loading && error ? (
        <div style={{ border: "1px solid rgba(239,68,68,0.4)", borderRadius: 12, padding: 12 }}>
          <strong>Error al cargar resultados</strong>
          <p style={{ marginBottom: 0 }}>{error}</p>
        </div>
      ) : null}
      {!loading && !error && filteredRuns.length === 0 ? (
        <div style={{ border: "1px dashed rgba(255,255,255,0.2)", borderRadius: 12, padding: 12 }}>
          No hay jobs que coincidan con los filtros.
        </div>
      ) : null}

      <DataTable
        rows={filteredRuns}
        rowKey={(r) => String(r.id)}
        columns={[
          {
            key: "display_name",
            header: "Nombre del resultado",
            render: (r) => (
              <RunDisplayNameEditor
                jobId={r.id}
                value={r.display_name ?? null}
                onSaved={handleRunDisplayNameSaved}
                compact
              />
            ),
          },
          {
            key: "scenario",
            header: "Escenario",
            render: (r) =>
              r.scenario_name ??
              (r.scenario_id === null
                ? (r.input_name ?? "CSV upload")
                : (scenarioMap[r.scenario_id]?.name ?? `#${r.scenario_id}`)),
          },
          {
            key: "run",
            header: "ID ejecución",
            render: (r) => <span style={{ fontFamily: "monospace", opacity: 0.75 }}>{r.id}</span>,
          },
          {
            key: "scenario_tag",
            header: "Etiqueta",
            render: (r) => {
              const tag = r.scenario_tag ?? (r.scenario_id != null ? scenarioMap[r.scenario_id]?.tag : null);
              return tag ? <ScenarioTagChip tag={tag} /> : <span style={{ opacity: 0.65 }}>—</span>;
            },
          },
          {
            key: "status",
            header: "Estado",
            render: (r) => {
              const { variant, label } = getSimulationRunStatusDisplay(r);
              return <Badge variant={variant}>{label}</Badge>;
            },
          },
          {
            key: "date",
            header: "Fecha",
            render: (r) => new Date(r.queued_at).toLocaleString(),
          },
          {
            key: "open",
            header: "Detalle",
            render: (r) => (
              <Link className="btn btn--ghost" to={paths.resultsDetail(r.id)}>
                Ver resultados
              </Link>
            ),
          },
        ]}
        searchableText={(r) =>
          `${r.id} ${r.scenario_id ?? ""} ${r.display_name ?? ""} ${r.scenario_name ?? ""}`
        }
      />
    </section>
  );
}

