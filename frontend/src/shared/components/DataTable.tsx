/**
 * Tabla de datos genérica con búsqueda en cliente y paginación configurable.
 * Soporta filtrado por texto cuando se provee searchableText.
 * Permite elegir 25, 50, 100 o 200 registros por página.
 */
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import { TextField } from "@/shared/components/TextField";

/** Definición de columna: clave, encabezado y función de renderizado por fila */
export type ColumnDef<T> = {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
};

type Props<T> = {
  rows: T[];
  columns: ColumnDef<T>[];
  rowKey: (row: T) => string;
  searchPlaceholder?: string;
  /** Si se provee, habilita el campo de búsqueda y filtra filas por este texto */
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

  /** Filas filtradas por búsqueda (si searchableText existe) */
  const filtered = useMemo(() => {
    if (!query.trim() || !searchableText) return rows;
    const q = query.trim().toLowerCase();
    return rows.filter((r) => searchableText(r).toLowerCase().includes(q));
  }, [query, rows, searchableText]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSizeState));
  const safePage = Math.min(page, totalPages);
  /** Rebanada de filas para la página actual */
  const paginated = filtered.slice((safePage - 1) * pageSizeState, safePage * pageSizeState);

  return (
    <div style={{ display: "grid", gap: 10 }}>
      {searchableText ? (
        <div style={{ maxWidth: 320 }}>
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

      <div style={{ overflowX: "auto", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12 }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead style={{ background: "rgba(255,255,255,0.03)" }}>
            <tr>
              {columns.map((c) => (
                <th key={c.key} style={{ textAlign: "left", fontSize: 13, padding: "10px 12px", color: "var(--muted)" }}>
                  {c.header}
                </th>
              ))}
            </tr>
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
                <tr key={rowKey(row)} style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                  {columns.map((c) => (
                    <td key={c.key} style={{ padding: "10px 12px", verticalAlign: "top" }}>
                      {c.render(row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <small style={{ opacity: 0.75 }}>
            Página {safePage} de {totalPages}
          </small>
          <small style={{ opacity: 0.75 }}>
            · Mostrando {paginated.length} de {filtered.length} registros
          </small>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, opacity: 0.85 }}>
            Registros por página:
            <select
              value={pageSizeState}
              onChange={(e) => {
                const next = Number(e.target.value) || 25;
                setPageSizeState(next);
                setPage(1);
              }}
              style={{ padding: "2px 6px", borderRadius: 6, background: "transparent", color: "inherit" }}
            >
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
            </select>
          </label>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn--ghost" type="button" onClick={() => setPage((p) => Math.max(1, p - 1))}>
              Anterior
            </button>
            <button className="btn btn--ghost" type="button" onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>
              Siguiente
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

