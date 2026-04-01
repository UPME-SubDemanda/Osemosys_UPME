import type { SimulationRun } from "@/types/domain";

type BadgeVariant = "success" | "danger" | "warning";

/** Etiqueta y variante para listados de simulaciones (tablas / home). */
export function getSimulationRunStatusDisplay(run: SimulationRun): { variant: BadgeVariant; label: string } {
  switch (run.status) {
    case "QUEUED":
      return { variant: "warning", label: "En cola" };
    case "RUNNING":
      return { variant: "warning", label: "En ejecución" };
    case "FAILED":
      return { variant: "danger", label: "Fallida" };
    case "CANCELLED":
      return { variant: "danger", label: "Cancelada" };
    case "SUCCEEDED":
      if (run.is_infeasible_result) {
        return { variant: "danger", label: "Infactible" };
      }
      return { variant: "success", label: "Exitosa" };
    default:
      return { variant: "warning", label: run.status };
  }
}
