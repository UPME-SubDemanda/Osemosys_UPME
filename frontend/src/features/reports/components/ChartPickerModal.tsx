/**
 * Modal reutilizable para seleccionar una gráfica guardada.
 * Uso:
 *   - Reemplazar un ítem en un reporte (dashboard o generador).
 *   - Agregar una nueva gráfica a un reporte.
 * Se puede filtrar por `compatibleWith`: si se pasa una plantilla, solo
 * muestra las que comparten compare_mode + num_scenarios (para reemplazo
 * preservando asignación de escenarios).
 */
import { useMemo, useState } from "react";
import type { SavedChartTemplate } from "@/types/domain";

type Props = {
  open: boolean;
  onClose: () => void;
  templates: SavedChartTemplate[];
  /** Si se pasa, filtra por compare_mode + num_scenarios iguales. */
  compatibleWith?: SavedChartTemplate | null | undefined;
  /** IDs a excluir (ej. ya seleccionados en el reporte). */
  excludeIds?: Set<number> | number[] | undefined;
  onPick: (tpl: SavedChartTemplate) => void;
  title?: string;
};

export function ChartPickerModal({
  open,
  onClose,
  templates,
  compatibleWith,
  excludeIds,
  onPick,
  title = "Elegir gráfica guardada",
}: Props) {
  const [query, setQuery] = useState("");
  const excludeSet = useMemo(() => {
    if (!excludeIds) return new Set<number>();
    return excludeIds instanceof Set ? excludeIds : new Set(excludeIds);
  }, [excludeIds]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return templates.filter((t) => {
      if (excludeSet.has(t.id)) return false;
      if (compatibleWith) {
        if (t.compare_mode !== compatibleWith.compare_mode) return false;
        if (t.num_scenarios !== compatibleWith.num_scenarios) return false;
      }
      if (!q) return true;
      const haystack = [t.name, t.tipo, t.description ?? "", t.owner_username ?? ""]
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [templates, excludeSet, compatibleWith, query]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl max-h-[80vh] flex flex-col rounded-xl border border-slate-800 bg-slate-950 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
          <div>
            <h3 className="m-0 text-sm font-semibold text-white">{title}</h3>
            {compatibleWith ? (
              <p className="m-0 mt-0.5 text-[11px] text-slate-500">
                Filtrando por plantillas compatibles ({compatibleWith.compare_mode} ·{" "}
                {compatibleWith.num_scenarios} escenario
                {compatibleWith.num_scenarios === 1 ? "" : "s"}).
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-700 px-2 py-1 text-xs text-slate-400 hover:bg-slate-800"
          >
            Cerrar
          </button>
        </header>
        <div className="p-3 border-b border-slate-800">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar por nombre, tipo o dueño…"
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600"
          />
        </div>
        <div className="overflow-y-auto flex-1 p-3 space-y-2">
          {filtered.length === 0 ? (
            <p className="m-0 text-center text-xs text-slate-500 py-6">
              No hay gráficas {query ? "que coincidan con la búsqueda" : "compatibles"}.
            </p>
          ) : (
            filtered.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => {
                  onPick(t);
                  onClose();
                }}
                className="w-full text-left rounded-lg border border-slate-800 bg-slate-900/40 hover:bg-slate-900/70 hover:border-cyan-500/40 px-3 py-2.5 transition-colors"
              >
                <div className="flex items-center gap-2 flex-wrap">
                  {t.is_favorite ? (
                    <span style={{ color: "#fbbf24" }} className="text-sm leading-none">★</span>
                  ) : null}
                  <span className="text-sm font-semibold text-white break-words">
                    {t.name}
                  </span>
                  {t.report_title ? (
                    <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2 py-0.5 text-[10px] font-semibold text-cyan-300">
                      Título: {t.report_title}
                    </span>
                  ) : null}
                  {t.is_public ? (
                    <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-300">
                      Público
                    </span>
                  ) : null}
                  {!t.is_owner ? (
                    <span className="rounded-full border border-slate-700 bg-slate-800/60 px-2 py-0.5 text-[10px] font-semibold text-slate-400">
                      de {t.owner_username ?? "otro"}
                    </span>
                  ) : null}
                </div>
                <p className="m-0 mt-1 text-[11px] text-slate-500">
                  {t.tipo} · {t.un}
                  {t.compare_mode === "facet"
                    ? ` · facet ${t.num_scenarios} esc.`
                    : " · 1 esc."}
                </p>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
