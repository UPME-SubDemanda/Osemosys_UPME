/**
 * Tabla de datos genérica con búsqueda global, filtro por columna y paginación.
 *
 * Cada columna puede declarar un filtro independiente:
 *   - `filter: { type: 'text' }`    → input de texto (busca "contains")
 *   - `filter: { type: 'select', options }` → dropdown con opciones
 * Ambos casos requieren `getFilterValue(row)` (o, por defecto, usa el mismo
 * `render` convertido a string — pero es mejor definirlo explícitamente).
 */
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import { TextField } from "@/shared/components/TextField";

export type ColumnFilterConfig<T> = {
  type: "text" | "select";
  /** Valor que se evalúa para el filtro (cadena) */
  getValue: (row: T) => string;
  /** Opciones cuando type='select' (value = label) */
  options?: { value: string; label: string }[];
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
  /** Filtro por columna: columnKey → string (vacío = sin filtro). */
  const [columnFilters, setColumnFilters] = useState<Record<string, string>>({});

  const hasColumnFilters = useMemo(
    () => columns.some((c) => c.filter),
    [columns],
  );

  /** Filtra: búsqueda global + filtros por columna. */
  const filtered = useMemo(() => {
    let out = rows;
    if (query.trim() && searchableText) {
      const q = query.trim().toLowerCase();
      out = out.filter((r) => searchableText(r).toLowerCase().includes(q));
    }
    for (const c of columns) {
      if (!c.filter) continue;
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
  }, [rows, query, searchableText, columns, columnFilters]);

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

  const clearAllFilters = () => {
    setQuery("");
    setColumnFilters({});
    setPage(1);
  };

  const anyFilterActive =
    query.trim().length > 0 || Object.keys(columnFilters).length > 0;

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
                      c.filter.type === "select" ? (
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
