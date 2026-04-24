/**
 * Heurística para elegir un job_id "representativo" cuando el usuario quiere
 * crear una gráfica nueva desde un contexto que no tiene job específico.
 *
 * Prioridad:
 *   1. Alguno de los escenarios seleccionados (preferredJobIds).
 *   2. Primer resultado favorito accesible.
 *   3. Primer resultado con etiqueta (`scenario_tag` o entrada en `scenario_tags`).
 *   4. Último resultado exitoso (queued_at más reciente).
 */
import type { SimulationRun } from "@/types/domain";

export function pickRepresentativeJob(
  available: SimulationRun[],
  preferredJobIds?: number[],
): SimulationRun | null {
  const usable = available.filter((j) => j.status === "SUCCEEDED" && !j.is_infeasible_result);
  if (usable.length === 0) return null;

  if (preferredJobIds && preferredJobIds.length > 0) {
    for (const jid of preferredJobIds) {
      const hit = usable.find((j) => j.id === jid);
      if (hit) return hit;
    }
  }

  const fav = usable.find((j) => j.is_favorite === true);
  if (fav) return fav;

  const tagged = usable.find(
    (j) => j.scenario_tag?.name || (j.scenario_tags && j.scenario_tags.length > 0),
  );
  if (tagged) return tagged;

  const sorted = [...usable].sort(
    (a, b) => new Date(b.queued_at).getTime() - new Date(a.queued_at).getTime(),
  );
  return sorted[0] ?? null;
}
