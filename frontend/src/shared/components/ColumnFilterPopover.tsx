/**
 * ColumnFilterPopover — popover de filtro por columna.
 *
 * Icono de embudo SVG que abre un popover con:
 *  - input de búsqueda (filtra localmente la lista de opciones)
 *  - botones "Todos" / "Ninguno"
 *  - lista scrollable de checkboxes
 *
 * El popover se renderiza en un portal con `position: fixed` para evitar ser
 * recortado por contenedores con `overflow: auto` (p.ej. la tabla wide
 * que usa scroll horizontal).
 */
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { WIDE_NULL_SENTINEL } from "@/features/scenarios/api/scenariosApi";

type Props = {
  columnLabel: string;
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
  loading?: boolean;
  /** Etiqueta visible personalizada para cada opción (p.ej. mapear id→nombre). */
  renderOption?: (value: string) => string;
};

/** Etiqueta por defecto: sentinel `__NULL__` se muestra como "(vacío)". */
function defaultOptionLabel(value: string): string {
  return value === WIDE_NULL_SENTINEL ? "(vacío)" : value;
}

type Pos = { top: number; left: number };

export function ColumnFilterPopover({
  columnLabel,
  options,
  selected,
  onChange,
  loading,
  renderOption,
}: Props) {
  const optionLabel = (v: string) => (renderOption ? renderOption(v) : defaultOptionLabel(v));
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [pos, setPos] = useState<Pos | null>(null);
  const btnRef = useRef<HTMLButtonElement | null>(null);
  const popoverRef = useRef<HTMLDivElement | null>(null);

  const computePos = () => {
    const el = btnRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    // Alinea bajo el botón; si se sale por la derecha, recuesta al borde.
    const popoverWidth = 260;
    const margin = 8;
    let left = rect.left;
    const maxLeft = window.innerWidth - popoverWidth - margin;
    if (left > maxLeft) left = Math.max(margin, maxLeft);
    setPos({ top: rect.bottom + 4, left });
  };

  useLayoutEffect(() => {
    if (open) computePos();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      const target = e.target as Node;
      if (btnRef.current?.contains(target)) return;
      if (popoverRef.current?.contains(target)) return;
      setOpen(false);
    };
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        // Capture phase + stopPropagation evitan que Escape llegue al input
        // interno (cuyo blur por defecto del navegador desplazaba la página)
        // o a otros handlers globales.
        e.stopPropagation();
        e.preventDefault();
        setOpen(false);
        // Devolvemos el foco al botón sin scroll automático del navegador.
        requestAnimationFrame(() => btnRef.current?.focus({ preventScroll: true }));
      }
    };
    const onScroll = () => computePos();
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onEsc, true);
    window.addEventListener("resize", onScroll);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onEsc, true);
      window.removeEventListener("resize", onScroll);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [open]);

  const visibleOptions = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => optionLabel(o).toLowerCase().includes(q));
  }, [options, query]);

  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const selectedCount = selected.length;

  const toggle = (value: string) => {
    if (selectedSet.has(value)) {
      onChange(selected.filter((v) => v !== value));
    } else {
      onChange([...selected, value]);
    }
  };

  const selectAllVisible = () => {
    const next = new Set(selected);
    for (const o of visibleOptions) next.add(o);
    onChange(Array.from(next));
  };

  const clearAll = () => onChange([]);

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        className={`col-filter-btn${selectedCount > 0 ? " col-filter-btn--active" : ""}`}
        aria-label={`Filtrar ${columnLabel}`}
        title={selectedCount > 0 ? `${selectedCount} seleccionado(s)` : `Filtrar ${columnLabel}`}
        onClick={() => setOpen((v) => !v)}
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <polygon points="3 4 21 4 14 12.5 14 20 10 18 10 12.5 3 4" />
        </svg>
        {selectedCount > 0 ? <span className="col-filter-badge">{selectedCount}</span> : null}
      </button>
      {open && pos
        ? createPortal(
            <div
              ref={popoverRef}
              className="col-filter-popover"
              role="dialog"
              aria-label={`Filtro ${columnLabel}`}
              style={{ top: pos.top, left: pos.left }}
            >
              <div className="col-filter-popover__head">
                <input
                  type="text"
                  className="col-filter-popover__search"
                  placeholder="Buscar..."
                  autoFocus
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>
              <div className="col-filter-popover__actions">
                <button type="button" className="col-filter-popover__link" onClick={selectAllVisible} disabled={loading}>
                  Todos {query.trim() ? "(visibles)" : ""}
                </button>
                <button type="button" className="col-filter-popover__link" onClick={clearAll} disabled={loading || selectedCount === 0}>
                  Ninguno
                </button>
              </div>
              <div className="col-filter-popover__list">
                {loading ? (
                  <div className="col-filter-popover__empty">Cargando…</div>
                ) : visibleOptions.length === 0 ? (
                  <div className="col-filter-popover__empty">Sin opciones</div>
                ) : (
                  visibleOptions.map((opt) => {
                    const checked = selectedSet.has(opt);
                    const isNull = opt === WIDE_NULL_SENTINEL;
                    return (
                      <label key={opt} className="col-filter-popover__item">
                        <input type="checkbox" checked={checked} onChange={() => toggle(opt)} />
                        <span style={isNull ? { fontStyle: "italic", opacity: 0.82 } : undefined}>
                          {optionLabel(opt)}
                        </span>
                      </label>
                    );
                  })
                )}
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
