/**
 * EditChartCardModal — Modal de edición de la **configuración del chart**
 * usado dentro del Dashboard de un Reporte.
 *
 * Permite cambiar:
 *   - Orden de series (custom_series_order).
 *   - Rango del eje Y (y_axis_min / y_axis_max).
 *
 * Comportamiento por dueño:
 *   - Si el usuario actual es dueño del template (``template.is_owner``):
 *     PATCH directo sobre ese template (mismo objeto se actualiza para
 *     todos los reportes y vistas que lo usen).
 *   - Si NO es dueño (gráfica de un tercero, p. ej. oficial):
 *     POST de un nuevo template (clon de campos + nuevos modificadores)
 *     y emite ``onTemplateReplaced(oldId, newId)`` para que el reporte
 *     reemplace la referencia en sus ``items`` y ``layout``.
 */
import { useMemo, useState } from "react";
import { savedChartsApi } from "../api/savedChartsApi";
import type {
  SavedChartTemplate,
  SavedChartTemplateCreate,
  SyntheticSeries,
} from "@/types/domain";
import { SeriesOrderModal } from "@/shared/charts/SeriesOrderModal";

interface EditChartCardModalProps {
  open: boolean;
  onClose: () => void;
  /** Template original a editar. */
  template: SavedChartTemplate;
  /**
   * Nombres de las series visibles en este momento (para el modal de orden).
   * Lista plana — la unión de nombres en facet/by-year se calcula desde el
   * card padre con la data ya cargada.
   */
  seriesNames: { name: string; color?: string | null | undefined }[];
  /** Callback cuando se actualizó in-place (mismo template_id). */
  onTemplateUpdated: (updated: SavedChartTemplate) => void;
  /** Callback cuando se creó un nuevo template y se debe reemplazar la
   * referencia ``oldId → newId`` en el reporte que contiene la card. */
  onTemplateReplaced: (oldId: number, newTemplate: SavedChartTemplate) => void;
}

export function EditChartCardModal({
  open,
  onClose,
  template,
  seriesNames,
  onTemplateUpdated,
  onTemplateReplaced,
}: EditChartCardModalProps) {
  // Inicializar con los valores actuales del template.
  const [order, setOrder] = useState<string[] | null>(
    template.custom_series_order && template.custom_series_order.length > 0
      ? [...template.custom_series_order]
      : null,
  );
  const [yMin, setYMin] = useState<string>(
    typeof template.y_axis_min === "number" ? String(template.y_axis_min) : "",
  );
  const [yMax, setYMax] = useState<string>(
    typeof template.y_axis_max === "number" ? String(template.y_axis_max) : "",
  );
  const [orderModalOpen, setOrderModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isOwner = Boolean(template.is_owner);

  const orderSummary = useMemo(() => {
    if (!order || order.length === 0) return "Orden natural";
    return `${order.length} series · ${order.slice(0, 3).join(" · ")}${order.length > 3 ? "…" : ""}`;
  }, [order]);

  const parseNum = (s: string): number | null => {
    const t = s.trim();
    if (t === "") return null;
    const n = Number(t);
    return Number.isFinite(n) ? n : null;
  };

  const buildPartial = () => {
    const yMinNum = parseNum(yMin);
    const yMaxNum = parseNum(yMax);
    return {
      custom_series_order: order && order.length > 0 ? order : null,
      y_axis_min: yMinNum,
      y_axis_max: yMaxNum,
    } as const;
  };

  const handleSave = async () => {
    setError(null);
    const partial = buildPartial();
    // Validación cruzada de rango.
    if (
      typeof partial.y_axis_min === "number" &&
      typeof partial.y_axis_max === "number" &&
      partial.y_axis_min >= partial.y_axis_max
    ) {
      setError("El mínimo del eje Y debe ser menor que el máximo.");
      return;
    }
    setSaving(true);
    try {
      if (isOwner) {
        const updated = await savedChartsApi.update(template.id, partial);
        onTemplateUpdated(updated);
        onClose();
      } else {
        // Clon: copiamos TODOS los campos del original + sobrescribimos los
        // modificadores. Marcamos como privada (no propagamos la visibilidad).
        const payload: SavedChartTemplateCreate = {
          name: `${template.name} (mi copia)`,
          description: template.description ?? null,
          tipo: template.tipo,
          un: template.un,
          sub_filtro: template.sub_filtro ?? null,
          loc: template.loc ?? null,
          variable: template.variable ?? null,
          agrupar_por: template.agrupar_por ?? null,
          view_mode: template.view_mode,
          compare_mode: template.compare_mode,
          bar_orientation: template.bar_orientation ?? null,
          facet_placement: template.facet_placement ?? null,
          facet_legend_mode: template.facet_legend_mode ?? null,
          num_scenarios: template.num_scenarios,
          legend_title: template.legend_title ?? null,
          filename_mode: template.filename_mode ?? null,
          report_title: template.report_title ?? null,
          years_to_plot: template.years_to_plot ?? null,
          synthetic_series: (template.synthetic_series as SyntheticSeries[] | null) ?? null,
          table_period_years: template.table_period_years ?? null,
          table_cumulative: template.table_cumulative ?? null,
          // Modificadores nuevos (los que el usuario está editando).
          custom_series_order: partial.custom_series_order,
          y_axis_min: partial.y_axis_min,
          y_axis_max: partial.y_axis_max,
        };
        const created = await savedChartsApi.create(payload);
        onTemplateReplaced(template.id, created);
        onClose();
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "No se pudo guardar.";
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-[400] flex items-center justify-center bg-slate-950/70 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md max-h-[85vh] overflow-y-auto rounded-xl border border-slate-700 bg-slate-900 text-slate-100 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 border-b border-slate-800 px-5 py-3">
          <div className="min-w-0">
            <h3 className="m-0 text-base font-semibold">Editar gráfica</h3>
            <p className="m-0 text-xs text-slate-400 break-words">
              {template.report_title || template.name}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-2xl leading-none text-slate-500 hover:text-slate-200"
            aria-label="Cerrar"
          >
            ×
          </button>
        </div>

        {/* Aviso de no-dueño */}
        {!isOwner ? (
          <div className="mx-5 mt-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
            <strong>No eres dueño de esta gráfica.</strong> Al guardar se
            creará una copia personal en tu cuenta y el reporte usará la copia
            (la gráfica original no se modifica).
          </div>
        ) : null}

        <div className="px-5 py-4 grid gap-4">
          {/* Orden de series */}
          <div>
            <p className="m-0 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Orden de series
            </p>
            <div className="mt-1 flex items-center gap-2">
              <button
                type="button"
                onClick={() => setOrderModalOpen(true)}
                disabled={seriesNames.length < 2}
                className="rounded border border-slate-700 bg-slate-800/50 px-3 py-1.5 text-xs font-medium text-slate-100 hover:bg-slate-700 disabled:opacity-40"
              >
                Cambiar orden…
              </button>
              {order && order.length > 0 ? (
                <button
                  type="button"
                  onClick={() => setOrder(null)}
                  className="text-[11px] text-cyan-400 hover:text-cyan-300 underline"
                >
                  restaurar natural
                </button>
              ) : null}
            </div>
            <p className="mt-1 text-[11px] text-slate-500 break-words">
              {orderSummary}
            </p>
          </div>

          {/* Rango Y */}
          <div>
            <p className="m-0 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Rango eje Y
            </p>
            <div className="mt-1 flex items-center gap-2">
              <input
                type="number"
                value={yMin}
                onChange={(e) => setYMin(e.target.value)}
                placeholder="auto (0)"
                className="w-28 rounded border border-slate-700 bg-slate-950/60 px-2 py-1 text-xs text-slate-100 placeholder:text-slate-600"
              />
              <span className="text-slate-600">–</span>
              <input
                type="number"
                value={yMax}
                onChange={(e) => setYMax(e.target.value)}
                placeholder="auto"
                className="w-28 rounded border border-slate-700 bg-slate-950/60 px-2 py-1 text-xs text-slate-100 placeholder:text-slate-600"
              />
              {yMin !== "" || yMax !== "" ? (
                <button
                  type="button"
                  onClick={() => {
                    setYMin("");
                    setYMax("");
                  }}
                  className="text-[11px] text-cyan-400 hover:text-cyan-300 underline ml-1"
                >
                  limpiar
                </button>
              ) : null}
            </div>
            <p className="mt-1 text-[10px] text-slate-500">
              Vacío = auto (0 para apilados, auto para líneas).
            </p>
          </div>

          {error ? (
            <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
              {error}
            </div>
          ) : null}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-slate-800 px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="rounded border border-slate-700 bg-slate-800/40 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-700 disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving}
            className="rounded bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            {saving ? "Guardando…" : isOwner ? "Guardar cambios" : "Crear copia y reemplazar"}
          </button>
        </div>
      </div>

      <SeriesOrderModal
        open={orderModalOpen}
        onClose={() => setOrderModalOpen(false)}
        series={seriesNames}
        currentOrder={order}
        onApply={(next) => setOrder(next)}
      />
    </div>
  );
}
