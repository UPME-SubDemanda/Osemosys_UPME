/**
 * Selector de qué escenarios globales (por índice 0-based) consume una fila
 * del reporte. Reutilizado por el Generador y el Dashboard.
 */
import type { SavedChartTemplate } from "@/types/domain";

export function RowScenarioPicker({
  tpl,
  effectiveSlots,
  globalScenariosLen,
  isOverride,
  onChange,
}: {
  tpl: SavedChartTemplate;
  effectiveSlots: number[];
  globalScenariosLen: number;
  isOverride: boolean;
  onChange: (slots: number[] | null) => void;
}) {
  const totalOptions = Math.max(globalScenariosLen, tpl.num_scenarios);
  const slotOptions = Array.from({ length: totalOptions }, (_, i) => i);
  const handle = (i: number, newIdx: number) => {
    const next = [...effectiveSlots];
    while (next.length < tpl.num_scenarios) next.push(next.length);
    next[i] = newIdx;
    onChange(next.slice(0, tpl.num_scenarios));
  };
  return (
    <div className="rounded-md border border-slate-800 bg-slate-950/30 p-2">
      <div className="flex items-center justify-between gap-2 mb-1">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Escenarios para esta gráfica{" "}
          <span className="text-slate-600 font-normal normal-case">
            ({tpl.num_scenarios} requerido{tpl.num_scenarios === 1 ? "" : "s"})
          </span>
        </span>
        {isOverride ? (
          <button
            type="button"
            onClick={() => onChange(null)}
            className="text-[10px] text-slate-400 hover:text-slate-200 underline underline-offset-2"
          >
            Restablecer default
          </button>
        ) : null}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {Array.from({ length: tpl.num_scenarios }).map((_, i) => {
          const current = effectiveSlots[i] ?? i;
          return (
            <label key={i} className="inline-flex items-center gap-1 rounded bg-slate-900/60 px-1.5 py-1">
              <span className="text-[10px] text-slate-500">Slot {i + 1} →</span>
              <select
                value={current}
                onChange={(e) => handle(i, Number(e.target.value))}
                className="rounded border border-slate-700 bg-slate-950 px-1 py-0.5 text-[11px] text-slate-100"
              >
                {slotOptions.map((opt) => (
                  <option key={opt} value={opt}>
                    Escenario {opt + 1}
                  </option>
                ))}
              </select>
            </label>
          );
        })}
      </div>
    </div>
  );
}
