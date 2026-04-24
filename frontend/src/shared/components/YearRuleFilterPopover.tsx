/**
 * YearRuleFilterPopover — filtro de una columna de año por regla sobre valor.
 *
 * Dropdown con:
 *  - operador: > < >= <= = ≠ non-zero zero
 *  - input de valor (oculto para non-zero / zero)
 *  - botones "Aplicar" y "Limpiar"
 *
 * Renderizado en un portal con `position: fixed` para escapar del scroll
 * horizontal de la tabla wide.
 */
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { YearRule, YearRuleOp } from "@/features/scenarios/api/scenariosApi";

type Props = {
  year: number;
  rule: YearRule | null;
  onChange: (next: YearRule | null) => void;
};

type Pos = { top: number; left: number };

const OPS: { value: YearRuleOp; label: string }[] = [
  { value: "gt", label: "> (mayor que)" },
  { value: "lt", label: "< (menor que)" },
  { value: "gte", label: "≥ (mayor o igual)" },
  { value: "lte", label: "≤ (menor o igual)" },
  { value: "eq", label: "= (igual)" },
  { value: "ne", label: "≠ (distinto)" },
  { value: "nonzero", label: "No cero" },
  { value: "zero", label: "Cero" },
];

const OP_SHORT: Record<YearRuleOp, string> = {
  gt: ">",
  lt: "<",
  gte: "≥",
  lte: "≤",
  eq: "=",
  ne: "≠",
  nonzero: "≠0",
  zero: "=0",
};

function needsValue(op: YearRuleOp): boolean {
  return op !== "nonzero" && op !== "zero";
}

function ruleSummary(r: YearRule): string {
  if (!needsValue(r.op)) return OP_SHORT[r.op];
  return `${OP_SHORT[r.op]} ${r.value ?? ""}`;
}

export function YearRuleFilterPopover({ year, rule, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<Pos | null>(null);
  const [op, setOp] = useState<YearRuleOp>(rule?.op ?? "gt");
  const [valueStr, setValueStr] = useState<string>(rule?.value != null ? String(rule.value) : "");
  const btnRef = useRef<HTMLButtonElement | null>(null);
  const popRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (open) {
      setOp(rule?.op ?? "gt");
      setValueStr(rule?.value != null ? String(rule.value) : "");
    }
  }, [open, rule]);

  const computePos = () => {
    const el = btnRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const popoverWidth = 260;
    const margin = 8;
    let left = rect.right - popoverWidth;
    if (left < margin) left = margin;
    const maxLeft = window.innerWidth - popoverWidth - margin;
    if (left > maxLeft) left = maxLeft;
    setPos({ top: rect.bottom + 4, left });
  };

  useLayoutEffect(() => {
    if (open) computePos();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      const t = e.target as Node;
      if (btnRef.current?.contains(t)) return;
      if (popRef.current?.contains(t)) return;
      setOpen(false);
    };
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
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

  const apply = () => {
    if (!needsValue(op)) {
      onChange({ op, value: null });
    } else {
      const n = Number(valueStr);
      if (!Number.isFinite(n)) return;
      onChange({ op, value: n });
    }
    setOpen(false);
  };

  const clear = () => {
    onChange(null);
    setOpen(false);
  };

  const active = !!rule;

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        className={`col-filter-btn${active ? " col-filter-btn--active" : ""}`}
        aria-label={`Filtro de valor para ${year}`}
        title={active && rule ? `${year}: ${ruleSummary(rule)}` : `Filtrar valores de ${year}`}
        onClick={() => setOpen((v) => !v)}
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <polygon points="3 4 21 4 14 12.5 14 20 10 18 10 12.5 3 4" />
        </svg>
        {active && rule ? <span className="col-filter-badge">{ruleSummary(rule)}</span> : null}
      </button>
      {open && pos
        ? createPortal(
            <div
              ref={popRef}
              className="col-filter-popover"
              role="dialog"
              aria-label={`Filtro de valor ${year}`}
              style={{ top: pos.top, left: pos.left }}
              onMouseDown={(e) => e.stopPropagation()}
            >
              <div style={{ fontSize: 12, opacity: 0.75, padding: "0 2px" }}>
                Regla para año <strong>{year}</strong>
              </div>
              <select
                className="col-filter-popover__search"
                value={op}
                onChange={(e) => setOp(e.target.value as YearRuleOp)}
              >
                {OPS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              {needsValue(op) ? (
                <input
                  type="number"
                  step="any"
                  className="col-filter-popover__search"
                  placeholder="Valor…"
                  value={valueStr}
                  onChange={(e) => setValueStr(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      apply();
                    }
                  }}
                />
              ) : null}
              <div className="col-filter-popover__actions" style={{ justifyContent: "space-between" }}>
                <button
                  type="button"
                  className="col-filter-popover__link"
                  onClick={clear}
                  disabled={!active}
                >
                  Limpiar
                </button>
                <button
                  type="button"
                  className="col-filter-popover__link"
                  onClick={apply}
                  disabled={needsValue(op) && !Number.isFinite(Number(valueStr))}
                  style={{ fontWeight: 600 }}
                >
                  Aplicar
                </button>
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
