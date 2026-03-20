/**
 * HomePage - Dashboard principal de la aplicación OSeMOSYS
 *
 * Muestra un resumen de bienvenida y dos secciones:
 * - Escenarios recientes: últimos 5 escenarios del usuario
 * - Simulaciones recientes: últimos 5 jobs de simulación con su estado
 *
 * Endpoints usados:
 * - scenariosApi.listScenarios({ cantidad: 5 })
 * - simulationApi.listRuns({ cantidad: 5, offset: 1 })
 *
 * Los datos se cargan solo cuando hay usuario autenticado.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useCurrentUser } from "@/app/providers/useCurrentUser";
import { scenariosApi } from "@/features/scenarios/api/scenariosApi";
import { simulationApi } from "@/features/simulation/api/simulationApi";
import { paths } from "@/routes/paths";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import type { Scenario, SimulationRun } from "@/types/domain";

export function HomePage() {
  const { user } = useCurrentUser();
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [recentRuns, setRecentRuns] = useState<SimulationRun[]>([]);

  // Carga escenarios y simulaciones recientes al montar, solo si hay usuario
  useEffect(() => {
    if (!user) return;
    void scenariosApi.listScenarios({ cantidad: 5 }).then((res) => setScenarios(res.data));
    void simulationApi.listRuns({ cantidad: 5, offset: 1 }).then((res) => setRecentRuns(res.data));
  }, [user]);

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <section
        style={{
          padding: 20,
          border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: 12,
          background: "linear-gradient(135deg, rgba(31,94,164,0.12), rgba(20,184,122,0.08))",
        }}
      >
        <h1 style={{ marginTop: 0, fontSize: 24 }}>
          Bienvenido{user ? `, ${user.username}` : ""}
        </h1>
        <p style={{ marginBottom: 0, opacity: 0.85 }}>
          Gestiona escenarios, catálogos, solicitudes de cambio y ejecuciones OSeMOSYS desde un flujo
          unificado.
        </p>
        <div style={{ marginTop: 16, display: "flex", gap: 8, flexWrap: "wrap" }}>
          <Link to={paths.scenarios} style={{ textDecoration: "none" }}>
            <Button variant="primary">Ir a escenarios</Button>
          </Link>
          <Link to={paths.simulation} style={{ textDecoration: "none" }}>
            <Button variant="ghost">Lanzar simulación</Button>
          </Link>
          <Link to={paths.results} style={{ textDecoration: "none" }}>
            <Button variant="ghost">Ver resultados</Button>
          </Link>
        </div>
      </section>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 16 }}>
        <section className="pageSection" style={{ display: "grid", gap: 10 }}>
          <h2 style={{ margin: 0, fontSize: 18 }}>Escenarios recientes</h2>
          {/* Renderizado condicional: mensaje vacío o lista de escenarios */}
          {scenarios.length === 0 ? (
            <p style={{ opacity: 0.7, margin: 0 }}>No hay escenarios aún.</p>
          ) : (
            <div style={{ display: "grid", gap: 6 }}>
              {scenarios.map((s) => (
                <Link
                  key={s.id}
                  to={paths.scenarioDetail(s.id)}
                  style={{
                    textDecoration: "none",
                    padding: "10px 12px",
                    borderRadius: 8,
                    border: "1px solid rgba(255,255,255,0.06)",
                    background: "rgba(255,255,255,0.02)",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>{s.name}</div>
                    {s.description ? (
                      <small style={{ opacity: 0.65 }}>{s.description}</small>
                    ) : null}
                  </div>
                  <small style={{ opacity: 0.5, whiteSpace: "nowrap" }}>
                    {new Date(s.created_at).toLocaleDateString()}
                  </small>
                </Link>
              ))}
            </div>
          )}
        </section>

        <section className="pageSection" style={{ display: "grid", gap: 10 }}>
          <h2 style={{ margin: 0, fontSize: 18 }}>Simulaciones recientes</h2>
          {recentRuns.length === 0 ? (
            <p style={{ opacity: 0.7, margin: 0 }}>No hay simulaciones aún.</p>
          ) : (
            <div style={{ display: "grid", gap: 6 }}>
              {recentRuns.map((r) => (
                <Link
                  key={r.id}
                  to={paths.resultsDetail(r.id)}
                  style={{
                    textDecoration: "none",
                    padding: "10px 12px",
                    borderRadius: 8,
                    border: "1px solid rgba(255,255,255,0.06)",
                    background: "rgba(255,255,255,0.02)",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontWeight: 600, fontSize: 14 }}>Job #{r.id}</span>
                    {/* Badge de estado: success=exitosa, danger=fallida/cancelada, warning=en cola/ejecución */}
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
                  </div>
                  <small style={{ opacity: 0.5, whiteSpace: "nowrap" }}>
                    {new Date(r.queued_at).toLocaleDateString()}
                  </small>
                </Link>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

