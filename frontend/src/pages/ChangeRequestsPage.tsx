/**
 * ChangeRequestsPage - Solicitudes de cambio de valores OSeMOSYS
 *
 * Dos secciones:
 * 1. Mis solicitudes: las que el usuario creó, con filtro por estado (PENDING, APPROVED, REJECTED)
 * 2. Pendientes por escenario: solicitudes que el usuario puede aprobar/rechazar (propietario o admin)
 *
 * Endpoints usados:
 * - scenariosApi.listMyChangeRequests()
 * - scenariosApi.listScenarios(), getEffectivePermission()
 * - scenariosApi.listPendingChangeRequests(scenarioId)
 * - scenariosApi.reviewChangeRequest(id, APPROVED|REJECTED)
 *
 * Solo escenarios donde el usuario es owner o can_edit_direct muestran pendientes a revisar.
 */
import { useEffect, useMemo, useState } from "react";
import { useCurrentUser } from "@/app/providers/useCurrentUser";
import { useToast } from "@/app/providers/useToast";
import { scenariosApi } from "@/features/scenarios/api/scenariosApi";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { DataTable } from "@/shared/components/DataTable";
import type { ChangeRequest, ChangeRequestStatus, Scenario } from "@/types/domain";

const statusVariant: Record<ChangeRequestStatus, "warning" | "success" | "danger"> = {
  PENDING: "warning",
  APPROVED: "success",
  REJECTED: "danger",
};

export function ChangeRequestsPage() {
  const { user } = useCurrentUser();
  const { push } = useToast();
  const [myRequests, setMyRequests] = useState<ChangeRequest[]>([]);
  const [pendingByOwner, setPendingByOwner] = useState<ChangeRequest[]>([]);
  const [statusFilter, setStatusFilter] = useState<ChangeRequestStatus | "ALL">("ALL");
  const [scenarioIndex, setScenarioIndex] = useState<Record<number, Scenario>>({});

  // Carga mis solicitudes y las pendientes de escenarios que el usuario puede revisar
  useEffect(() => {
    if (!user) return;
    Promise.all([scenariosApi.listMyChangeRequests(), scenariosApi.listScenarios()])
      .then(async ([mine, scenarioRes]) => {
        const scenarios = scenarioRes.data;
        setMyRequests(mine);
        setScenarioIndex(Object.fromEntries(scenarios.map((s) => [s.id, s])));

        // Obtener escenarios donde el usuario puede aprobar/rechazar solicitudes
        const reviewableChecks = await Promise.all(
          scenarios.map(async (s) => ({ scenario: s, access: await scenariosApi.getEffectivePermission(s, user) })),
        );
        const reviewable = reviewableChecks
          .filter((entry) => entry.access.isOwner || entry.access.can_edit_direct)
          .map((entry) => entry.scenario);

        const pendingLists = await Promise.all(reviewable.map((s) => scenariosApi.listPendingChangeRequests(s.id)));
        setPendingByOwner(pendingLists.flat());
      })
      .catch((err: unknown) => push(err instanceof Error ? err.message : "Error cargando solicitudes.", "error"));
  }, [push, user]);

  // Filtrado de mis solicitudes por estado seleccionado
  const filteredMine = useMemo(() => {
    if (statusFilter === "ALL") return myRequests;
    return myRequests.filter((r) => r.status === statusFilter);
  }, [myRequests, statusFilter]);

  /** Aprueba o rechaza una solicitud y recarga la lista de pendientes */
  async function review(id: number, decision: "APPROVED" | "REJECTED") {
    await scenariosApi.reviewChangeRequest(id, decision);
    const pendingLists = await Promise.all(
      Object.values(scenarioIndex).map(async (scenario) => {
        try {
          return await scenariosApi.listPendingChangeRequests(scenario.id);
        } catch {
          return [];
        }
      }),
    );
    setPendingByOwner(pendingLists.flat());
    push(`Solicitud ${decision === "APPROVED" ? "aprobada" : "rechazada"}.`, "success");
  }

  return (
    <section style={{ display: "grid", gap: 14 }}>
      <article className="pageSection" style={{ display: "grid", gap: 10 }}>
        <div className="toolbarRow">
          <h1 style={{ margin: 0 }}>Mis solicitudes</h1>
          <label className="field" style={{ width: 220 }}>
            <span className="field__label">Filtrar por estado</span>
            <select
              className="field__input"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as ChangeRequestStatus | "ALL")}
            >
              <option value="ALL">Todos</option>
              <option value="PENDING">Pendiente</option>
              <option value="APPROVED">Aprobada</option>
              <option value="REJECTED">Rechazada</option>
            </select>
          </label>
        </div>

        <DataTable
          rows={filteredMine}
          rowKey={(r) => String(r.id)}
          columns={[
            { key: "id", header: "ID", render: (r) => r.id },
            { key: "param", header: "Valor OSeMOSYS (ID)", render: (r) => r.id_osemosys_param_value },
            { key: "by", header: "Creada por", render: (r) => r.created_by },
            { key: "values", header: "Cambio", render: (r) => `${r.old_value} → ${r.new_value}` },
            {
              key: "status",
              header: "Estado",
              render: (r) => (
                <Badge variant={statusVariant[r.status]}>
                  {r.status === "PENDING" ? "Pendiente" : r.status === "APPROVED" ? "Aprobada" : "Rechazada"}
                </Badge>
              ),
            },
            { key: "date", header: "Fecha", render: (r) => new Date(r.created_at).toLocaleString() },
          ]}
          searchableText={(r) => `${r.created_by} ${r.status}`}
        />
      </article>

      <article className="pageSection" style={{ display: "grid", gap: 10 }}>
        <h2 style={{ margin: 0 }}>Pendientes por escenario (propietario / administradores)</h2>
        <DataTable
          rows={pendingByOwner}
          rowKey={(r) => String(r.id)}
          columns={[
            { key: "id", header: "ID", render: (r) => r.id },
            { key: "req", header: "Solicitante", render: (r) => r.created_by },
            { key: "param", header: "Valor OSeMOSYS (ID)", render: (r) => r.id_osemosys_param_value },
            { key: "change", header: "Cambio", render: (r) => `${r.old_value} → ${r.new_value}` },
            {
              key: "actions",
              header: "Acciones",
              render: (r) => (
                <div style={{ display: "flex", gap: 8 }}>
                  <Button variant="primary" onClick={() => review(r.id, "APPROVED")}>
                    Aprobar
                  </Button>
                  <Button variant="ghost" onClick={() => review(r.id, "REJECTED")}>
                    Rechazar
                  </Button>
                </div>
              ),
            },
          ]}
          searchableText={(r) => `${r.created_by}`}
        />
      </article>
    </section>
  );
}

