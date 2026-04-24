/**
 * Popover para controlar visibilidad de columnas dimensión del Data Explorer.
 *
 * Modos por columna: "auto" (oculta si vacía) | "visible" (siempre) | "hidden" (nunca).
 * Incluye un toggle global "Auto-ocultar vacías" y un "Restablecer" a auto.
 */
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export type ColumnVisibilityMode = "auto" | "visible" | "hidden";

export type ColumnItem = {
  /** Identificador estable (p.ej. filterKey o "__scalar__") */
  id: string;
  label: string;
  /** Si true, la columna está actualmente vacía en los datos cargados. */
  isEmpty: boolean;
};

type Props = {
  columns: ColumnItem[];
  modes: Record<string, ColumnVisibilityMode>;
  autoHideEnabled: boolean;
  onChangeMode: (columnId: string, mode: ColumnVisibilityMode) => void;
  onToggleAutoHide: (enabled: boolean) => void;
  onResetAll: () => void;
};

type Pos = { top: number; left: number };

function triStateFromMode(
  mode: ColumnVisibilityMode,
  isEmpty: boolean,
): { checked: boolean; indeterminate: boolean } {
  if (mode === "visible") return { checked: true, indeterminate: false };
  if (mode === "hidden") return { checked: false, indeterminate: false };
  // auto
  if (isEmpty) return { checked: false, indeterminate: true };
  return { checked: true, indeterminate: true };
}

function nextModeOnClick(current: ColumnVisibilityMode): ColumnVisibilityMode {
  // Ciclo: auto → visible → hidden → auto
  if (current === "auto") return "visible";
  if (current === "visible") return "hidden";
  return "auto";
}

export function ColumnVisibilityPopover({
  columns,
  modes,
  autoHideEnabled,
  onChangeMode,
  onToggleAutoHide,
  onResetAll,
}: Props) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<Pos | null>(null);
  const btnRef = useRef<HTMLButtonElement | null>(null);
  const popoverRef = useRef<HTMLDivElement | null>(null);

  const hiddenCount = columns.filter((c) => {
    const m = modes[c.id] ?? "auto";
    return m === "hidden" || (m === "auto" && c.isEmpty && autoHideEnabled);
  }).length;

  const computePos = () => {
    const el = btnRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const popoverWidth = 320;
    const margin = 8;
    let left = rect.right - popoverWidth;
    if (left < margin) left = margin;
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
        e.preventDefault();
        setOpen(false);
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

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        title="Mostrar / ocultar columnas"
        className="btn btn--ghost"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          fontSize: 13,
        }}
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <path d="M9 3v18M15 3v18" />
        </svg>
        Columnas
        {hiddenCount > 0 ? (
          <span
            style={{
              padding: "1px 6px",
              fontSize: 11,
              borderRadius: 999,
              background: "rgba(80,140,255,0.25)",
              color: "rgba(220,230,255,0.95)",
            }}
          >
            {hiddenCount} ocultas
          </span>
        ) : null}
      </button>
      {open && pos
        ? createPortal(
            <div
              ref={popoverRef}
              role="dialog"
              aria-label="Visibilidad de columnas"
              style={{
                position: "fixed",
                top: pos.top,
                left: pos.left,
                width: 320,
                maxHeight: 460,
                overflowY: "auto",
                background: "rgba(18, 20, 26, 0.98)",
                border: "1px solid rgba(255,255,255,0.14)",
                borderRadius: 10,
                boxShadow: "0 12px 40px rgba(0,0,0,0.5)",
                padding: 10,
                zIndex: 10000,
                color: "inherit",
                fontSize: 13,
              }}
            >
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "4px 4px 8px",
                  borderBottom: "1px solid rgba(255,255,255,0.08)",
                  cursor: "pointer",
                }}
              >
                <input
                  type="checkbox"
                  checked={autoHideEnabled}
                  onChange={(e) => onToggleAutoHide(e.target.checked)}
                />
                <span>Auto-ocultar columnas vacías</span>
              </label>

              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  padding: "6px 4px 4px",
                }}
              >
                <small style={{ opacity: 0.65 }}>
                  Click en el label para alternar auto/visible/oculta
                </small>
                <button
                  type="button"
                  onClick={onResetAll}
                  style={{
                    background: "transparent",
                    border: "none",
                    color: "rgba(120,170,255,0.95)",
                    cursor: "pointer",
                    fontSize: 12,
                    padding: 0,
                  }}
                >
                  Restablecer
                </button>
              </div>

              <ul
                style={{
                  listStyle: "none",
                  margin: 0,
                  padding: 0,
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                {columns.map((col) => {
                  const mode = modes[col.id] ?? "auto";
                  const tri = triStateFromMode(mode, col.isEmpty);
                  const onToggle = () => onChangeMode(col.id, nextModeOnClick(mode));
                  return (
                    <li key={col.id}>
                      <button
                        type="button"
                        onClick={onToggle}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 10,
                          width: "100%",
                          padding: "6px 4px",
                          background: "transparent",
                          border: "none",
                          color: "inherit",
                          cursor: "pointer",
                          textAlign: "left",
                          fontSize: 13,
                        }}
                        title={
                          mode === "auto"
                            ? `Auto${col.isEmpty ? " (actualmente oculta: vacía)" : " (actualmente visible)"}`
                            : mode === "visible"
                              ? "Forzar visible"
                              : "Forzar oculta"
                        }
                      >
                        <input
                          type="checkbox"
                          readOnly
                          checked={tri.checked}
                          ref={(el) => {
                            if (el) el.indeterminate = tri.indeterminate;
                          }}
                          style={{ pointerEvents: "none" }}
                        />
                        <span style={{ flex: 1 }}>{col.label}</span>
                        <span
                          style={{
                            fontSize: 11,
                            opacity: 0.65,
                            minWidth: 56,
                            textAlign: "right",
                          }}
                        >
                          {mode === "auto"
                            ? col.isEmpty && autoHideEnabled
                              ? "auto (oc)"
                              : "auto"
                            : mode}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
