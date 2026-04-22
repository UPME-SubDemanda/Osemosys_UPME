/**
 * Tabla de datos genérica con búsqueda global, filtro por columna y paginación.
 *
 * Cada columna puede declarar un filtro independiente:
 *   - `filter: { type: 'text' }`         → input de texto (busca "contains")
 *   - `filter: { type: 'select', options }` → dropdown single-select
 *   - `filter: { type: 'multiselect' }`  → dropdown con búsqueda + checkboxes.
 *       Las opciones se auto-derivan de los valores únicos devueltos por
 *       `getValue(row)`; si se pasan `options`, se usa ese catálogo fijo
 *       y además se garantiza que aparezcan las opciones aún sin datos.
 * Todos los casos requieren `getValue(row)` (cadena).
 */
import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { TextField } from "@/shared/components/TextField";

export type ColumnFilterConfig<T> = {
  type: "text" | "select" | "multiselect";
  /** Valor que se evalúa para el filtro (cadena) */
  getValue: (row: T) => string;
  /** Opciones cuando type='select' o para extender multiselect */
  options?: { value: string; label: string }[];
  /** Label opcional al renderizar un valor como chip/opción (multiselect). */
  getLabel?: (value: string) => string;
  placeholder?: string;
};

/** Definición de columna: clave, encabezado y función de renderizado por fila */
export type ColumnDef<T> = {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  filter?: ColumnFilterConfig<T>;
};

type Props<T> = {
  rows: T[];
  columns: ColumnDef<T>[];
  rowKey: (row: T) => string;
  searchPlaceholder?: string;
  /** Si se provee, habilita el campo de búsqueda global */
  searchableText?: (row: T) => string;
  pageSize?: number;
};

export function DataTable<T>({
  rows,
  columns,
  rowKey,
  searchPlaceholder = "Buscar...",
  searchableText,
  pageSize = 25,
}: Props<T>) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [pageSizeState, setPageSizeState] = useState(pageSize);
  /** Filtros text + single-select: columnKey → string. */
  const [columnFilters, setColumnFilters] = useState<Record<string, string>>({});
  /** Filtros multiselect: columnKey → array de valores seleccionados (OR). */
  const [multiFilters, setMultiFilters] = useState<Record<string, string[]>>({});

  const hasColumnFilters = useMemo(
    () => columns.some((c) => c.filter),
    [columns],
  );

  /** Opciones auto-derivadas de los datos por cada columna multiselect. */
  const multiOptionsByKey = useMemo(() => {
    const byKey: Record<string, { value: string; label: string }[]> = {};
    for (const c of columns) {
      if (!c.filter || c.filter.type !== "multiselect") continue;
      const seen = new Set<string>();
      const opts: { value: string; label: string }[] = [];
      for (const o of c.filter.options ?? []) {
        if (!seen.has(o.value)) {
          seen.add(o.value);
          opts.push(o);
        }
      }
      for (const r of rows) {
        const v = c.filter.getValue(r);
        if (!v || seen.has(v)) continue;
        seen.add(v);
        opts.push({ value: v, label: c.filter.getLabel?.(v) ?? v });
      }
      opts.sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: "base" }));
      byKey[c.key] = opts;
    }
    return byKey;
  }, [columns, rows]);

  /** Filtra: búsqueda global + filtros por columna. */
  const filtered = useMemo(() => {
    let out = rows;
    if (query.trim() && searchableText) {
      const q = query.trim().toLowerCase();
      out = out.filter((r) => searchableText(r).toLowerCase().includes(q));
    }
    for (const c of columns) {
      if (!c.filter) continue;
      if (c.filter.type === "multiselect") {
        const selected = multiFilters[c.key];
        if (!selected || selected.length === 0) continue;
        const set = new Set(selected);
        out = out.filter((r) => set.has(c.filter!.getValue(r)));
        continue;
      }
      const raw = (columnFilters[c.key] ?? "").trim();
      if (!raw) continue;
      const needle = raw.toLowerCase();
      const matcher =
        c.filter.type === "select"
          ? (r: T) => c.filter!.getValue(r).toLowerCase() === needle
          : (r: T) => c.filter!.getValue(r).toLowerCase().includes(needle);
      out = out.filter(matcher);
    }
    return out;
  }, [rows, query, searchableText, columns, columnFilters, multiFilters]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSizeState));
  const safePage = Math.min(page, totalPages);
  const paginated = filtered.slice(
    (safePage - 1) * pageSizeState,
    safePage * pageSizeState,
  );

  const setFilter = (key: string, value: string) => {
    setPage(1);
    setColumnFilters((prev) => {
      if (!value) {
        const next = { ...prev };
        delete next[key];
        return next;
      }
      return { ...prev, [key]: value };
    });
  };

  const setMulti = (key: string, values: string[]) => {
    setPage(1);
    setMultiFilters((prev) => {
      if (values.length === 0) {
        const next = { ...prev };
        delete next[key];
        return next;
      }
      return { ...prev, [key]: values };
    });
  };

  const clearAllFilters = () => {
    setQuery("");
    setColumnFilters({});
    setMultiFilters({});
    setPage(1);
  };

  const anyFilterActive =
    query.trim().length > 0 ||
    Object.keys(columnFilters).length > 0 ||
    Object.values(multiFilters).some((v) => v.length > 0);

  return (
    <div style={{ display: "grid", gap: 10 }}>
      {searchableText || hasColumnFilters ? (
        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            gap: 12,
            flexWrap: "wrap",
          }}
        >
          {searchableText ? (
            <div style={{ maxWidth: 320, flex: "1 1 220px" }}>
              <TextField
                label="Buscar"
                value={query}
                onChange={(e) => {
                  setPage(1);
                  setQuery(e.target.value);
                }}
                placeholder={searchPlaceholder}
              />
            </div>
          ) : null}
          {anyFilterActive ? (
            <button
              className="btn btn--ghost"
              type="button"
              onClick={clearAllFilters}
              style={{ alignSelf: "flex-end" }}
            >
              Limpiar filtros
            </button>
          ) : null}
        </div>
      ) : null}

      <div
        style={{
          overflowX: "auto",
          border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: 12,
        }}
      >
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead style={{ background: "rgba(255,255,255,0.03)" }}>
            <tr>
              {columns.map((c) => (
                <th
                  key={c.key}
                  style={{
                    textAlign: "left",
                    fontSize: 13,
                    padding: "10px 12px",
                    color: "var(--muted)",
                  }}
                >
                  {c.header}
                </th>
              ))}
            </tr>
            {hasColumnFilters ? (
              <tr style={{ background: "rgba(255,255,255,0.015)" }}>
                {columns.map((c) => (
                  <th
                    key={`${c.key}-filter`}
                    style={{ padding: "6px 10px", verticalAlign: "top" }}
                  >
                    {c.filter ? (
                      c.filter.type === "multiselect" ? (
                        <MultiSelectFilter
                          options={multiOptionsByKey[c.key] ?? []}
                          selected={multiFilters[c.key] ?? []}
                          onChange={(values) => setMulti(c.key, values)}
                          placeholder={c.filter.placeholder ?? "Filtrar…"}
                        />
                      ) : c.filter.type === "select" ? (
                        <select
                          value={columnFilters[c.key] ?? ""}
                          onChange={(e) => setFilter(c.key, e.target.value)}
                          style={{
                            width: "100%",
                            padding: "4px 6px",
                            borderRadius: 6,
                            border: "1px solid rgba(255,255,255,0.15)",
                            background: "rgba(15,23,42,0.6)",
                            color: "inherit",
                            fontSize: 12,
                          }}
                        >
                          <option value="">Todos</option>
                          {(c.filter.options ?? []).map((o) => (
                            <option key={o.value} value={o.value}>
                              {o.label}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type="text"
                          value={columnFilters[c.key] ?? ""}
                          onChange={(e) => setFilter(c.key, e.target.value)}
                          placeholder={c.filter.placeholder ?? "Filtrar…"}
                          style={{
                            width: "100%",
                            padding: "4px 6px",
                            borderRadius: 6,
                            border: "1px solid rgba(255,255,255,0.15)",
                            background: "rgba(15,23,42,0.6)",
                            color: "inherit",
                            fontSize: 12,
                          }}
                        />
                      )
                    ) : null}
                  </th>
                ))}
              </tr>
            ) : null}
          </thead>
          <tbody>
            {paginated.length === 0 ? (
              <tr>
                <td colSpan={columns.length} style={{ padding: 14, opacity: 0.75 }}>
                  Sin registros.
                </td>
              </tr>
            ) : (
              paginated.map((row) => (
                <tr
                  key={rowKey(row)}
                  style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}
                >
                  {columns.map((c) => (
                    <td
                      key={c.key}
                      style={{ padding: "10px 12px", verticalAlign: "top" }}
                    >
                      {c.render(row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <small style={{ opacity: 0.75 }}>
            Página {safePage} de {totalPages}
          </small>
          <small style={{ opacity: 0.75 }}>
            · Mostrando {paginated.length} de {filtered.length} registros
          </small>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 13,
              opacity: 0.85,
            }}
          >
            Registros por página:
            <select
              value={pageSizeState}
              onChange={(e) => {
                const next = Number(e.target.value) || 25;
                setPageSizeState(next);
                setPage(1);
              }}
              style={{
                padding: "2px 6px",
                borderRadius: 6,
                background: "transparent",
                color: "inherit",
              }}
            >
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
            </select>
          </label>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              className="btn btn--ghost"
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Anterior
            </button>
            <button
              className="btn btn--ghost"
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Siguiente
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/** Dropdown compacto: botón con resumen + popover con búsqueda y checkboxes. */
function MultiSelectFilter({
  options,
  selected,
  onChange,
  placeholder,
}: {
  options: { value: string; label: string }[];
  selected: string[];
  onChange: (next: string[]) => void;
  placeholder: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const filteredOpts = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => o.label.toLowerCase().includes(q));
  }, [options, query]);

  const summary =
    selected.length === 0
      ? placeholder
      : selected.length === 1
        ? options.find((o) => o.value === selected[0])?.label ?? selected[0]
        : `${selected.length} seleccionados`;

  const toggle = (value: string) => {
    if (selectedSet.has(value)) {
      onChange(selected.filter((v) => v !== value));
    } else {
      onChange([...selected, value]);
    }
  };

  return (
    <div ref={rootRef} style={{ position: "relative" }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 6,
          padding: "4px 6px",
          borderRadius: 6,
          border: "1px solid rgba(255,255,255,0.15)",
          background: "rgba(15,23,42,0.6)",
          color: "inherit",
          fontSize: 12,
          cursor: "pointer",
          textAlign: "left",
        }}
      >
        <span
          style={{
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            opacity: selected.length === 0 ? 0.65 : 1,
          }}
        >
          {summary}
        </span>
        <span style={{ opacity: 0.7, fontSize: 10 }}>{open ? "▴" : "▾"}</span>
      </button>
      {open ? (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            left: 0,
            right: 0,
            minWidth: 180,
            zIndex: 30,
            background: "#0f172a",
            border: "1px solid rgba(255,255,255,0.2)",
            borderRadius: 10,
            padding: 6,
            maxHeight: 280,
            overflowY: "auto",
            boxShadow: "0 10px 30px rgba(0,0,0,0.4)",
          }}
        >
          <input
            autoFocus
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar…"
            style={{
              width: "100%",
              padding: "4px 6px",
              borderRadius: 6,
              border: "1px solid rgba(255,255,255,0.15)",
              background: "rgba(15,23,42,0.85)",
              color: "inherit",
              fontSize: 12,
              marginBottom: 4,
            }}
          />
          <div style={{ display: "flex", gap: 6, marginBottom: 4 }}>
            <button
              type="button"
              className="btn btn--ghost"
              style={{ flex: 1, fontSize: 11, padding: "2px 6px" }}
              onClick={() => onChange(filteredOpts.map((o) => o.value))}
            >
              Todos
            </button>
            <button
              type="button"
              className="btn btn--ghost"
              style={{ flex: 1, fontSize: 11, padding: "2px 6px" }}
              onClick={() => onChange([])}
            >
              Ninguno
            </button>
          </div>
          {filteredOpts.length === 0 ? (
            <div style={{ fontSize: 12, opacity: 0.6, padding: "6px 4px" }}>
              Sin coincidencias
            </div>
          ) : (
            filteredOpts.map((o) => {
              const checked = selectedSet.has(o.value);
              return (
                <label
                  key={o.value}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "4px 6px",
                    borderRadius: 6,
                    cursor: "pointer",
                    fontSize: 12,
                    background: checked ? "rgba(56,189,248,0.12)" : "transparent",
                  }}
                  onMouseEnter={(e) => {
                    if (!checked)
                      e.currentTarget.style.background = "rgba(255,255,255,0.05)";
                  }}
                  onMouseLeave={(e) => {
                    if (!checked) e.currentTarget.style.background = "transparent";
                  }}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggle(o.value)}
                  />
                  <span
                    style={{
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {o.label}
                  </span>
                </label>
              );
            })
          )}
        </div>
      ) : null}
    </div>
  );
}
