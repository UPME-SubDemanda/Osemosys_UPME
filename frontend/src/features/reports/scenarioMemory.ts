/**
 * Persistencia client-side de los escenarios seleccionados por reporte.
 *
 * Guarda en localStorage bajo la clave `report-scenarios:<reportId>` la lista
 * de job_ids (o nulls) que el usuario eligió la última vez. Al volver a abrir
 * el reporte (Generador o Dashboard), se pre-pueblan esos slots.
 */

const KEY_PREFIX = "osemosys-report-scenarios:";

function keyFor(reportId: number | string | null | undefined): string | null {
  if (reportId == null) return null;
  const n = typeof reportId === "number" ? reportId : Number(reportId);
  if (!Number.isFinite(n) || n <= 0) return null;
  return `${KEY_PREFIX}${n}`;
}

/** Devuelve los job_ids guardados para el reporte, o null si no hay. */
export function loadReportScenarios(
  reportId: number | string | null | undefined,
): (number | null)[] | null {
  const k = keyFor(reportId);
  if (!k) return null;
  try {
    const raw = localStorage.getItem(k);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return null;
    return parsed.map((v) =>
      typeof v === "number" && Number.isFinite(v) ? v : null,
    );
  } catch {
    return null;
  }
}

/** Persiste los escenarios actuales del reporte. */
export function saveReportScenarios(
  reportId: number | string | null | undefined,
  scenarios: (number | null)[],
): void {
  const k = keyFor(reportId);
  if (!k) return;
  try {
    localStorage.setItem(k, JSON.stringify(scenarios));
  } catch {
    /* ignore (quota exceeded, etc.) */
  }
}

/** Limpia la memoria de un reporte específico (ej. al eliminarlo). */
export function clearReportScenarios(
  reportId: number | string | null | undefined,
): void {
  const k = keyFor(reportId);
  if (!k) return;
  try {
    localStorage.removeItem(k);
  } catch {
    /* ignore */
  }
}
