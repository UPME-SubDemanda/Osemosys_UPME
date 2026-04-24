/**
 * Persistencia local de series sintéticas (overlays manuales) por contexto de
 * gráfica. La clave es una "firma" determinista que mezcla tipo/unidad/filtros:
 * dos sesiones con la misma configuración recuperan las mismas series.
 *
 * Se usa `localStorage` y no el backend porque las series viven antes de
 * decidir guardarlas como plantilla — si el usuario eventualmente guarda el
 * chart como `SavedChartTemplate`, las series viajan también al payload y
 * quedan persistidas en BD.
 */
import type { SyntheticSeries } from "@/types/domain";

const PREFIX = "osemosys:synthetic-series:";
/** Protege localStorage contra corrupción / cuotas. */
const MAX_PAYLOAD_BYTES = 512 * 1024;

/**
 * Construye una firma determinista del contexto de la gráfica. Incluye los
 * campos que afectan la semántica de los overlays (unidad, filtros, compare
 * mode). No incluye `years_to_plot` — cambiar los años a mostrar en modo
 * by-year no invalida las series pre-existentes.
 */
export function syntheticSeriesSignature(parts: {
  tipo: string;
  un: string;
  sub_filtro?: string | null | undefined;
  loc?: string | null | undefined;
  variable?: string | null | undefined;
  agrupar_por?: string | null | undefined;
  view_mode?: string | null | undefined;
  compare_mode: string;
}): string {
  return [
    parts.tipo,
    parts.un,
    parts.sub_filtro ?? "",
    parts.loc ?? "",
    parts.variable ?? "",
    parts.agrupar_por ?? "",
    parts.view_mode ?? "",
    parts.compare_mode,
  ].join("|");
}

export function loadSyntheticSeries(signature: string): SyntheticSeries[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(PREFIX + signature);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed as SyntheticSeries[];
  } catch (err) {
    console.warn("No se pudieron cargar series sintéticas:", err);
    return [];
  }
}

export function saveSyntheticSeries(
  signature: string,
  series: SyntheticSeries[],
): void {
  if (typeof window === "undefined") return;
  try {
    if (series.length === 0) {
      window.localStorage.removeItem(PREFIX + signature);
      return;
    }
    const payload = JSON.stringify(series);
    if (payload.length > MAX_PAYLOAD_BYTES) {
      console.warn(
        `Series sintéticas demasiado grandes (${payload.length} bytes), omitiendo persistencia.`,
      );
      return;
    }
    window.localStorage.setItem(PREFIX + signature, payload);
  } catch (err) {
    console.warn("No se pudieron guardar series sintéticas:", err);
  }
}
