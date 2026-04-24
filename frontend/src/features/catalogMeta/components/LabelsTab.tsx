/**
 * LabelsTab — administración de etiquetas (Fase 3.3.B).
 *
 * Paginación server-side (~740 entries), búsqueda full-text en código y
 * label, filtro por categoría, edición inline.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  catalogMetaApi,
  type LabelItem,
} from "@/features/catalogMeta/api/catalogMetaApi";
import { Button } from "@/shared/components/Button";

const PAGE_SIZES = [25, 50, 100, 200] as const;

type Draft = Partial<LabelItem> & { _saving?: boolean };

export function LabelsTab() {
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [category, setCategory] = useState<string>("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(50);

  const [rows, setRows] = useState<LabelItem[]>([]);
  const [total, setTotal] = useState(0);
  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<number, Draft>>({});
  const [creating, setCreating] = useState<CreateDraft | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Parameters<typeof catalogMetaApi.listLabels>[0] = {
        offset: (page - 1) * pageSize,
        limit: pageSize,
      };
      if (search) params.search = search;
      if (category) params.category = category;
      const resp = await catalogMetaApi.listLabels(params);
      setRows(resp.items);
      setTotal(resp.total);
      setCategories(resp.categories);
      setDraft({});
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error cargando etiquetas");
    } finally {
      setLoading(false);
    }
  }, [search, category, page, pageSize]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize]);

  const setField = (id: number, patch: Partial<LabelItem>) =>
    setDraft((prev) => ({ ...prev, [id]: { ...(prev[id] ?? {}), ...patch } }));

  const save = async (row: LabelItem) => {
    const d = draft[row.id];
    if (!d) return;
    setDraft((prev) => ({ ...prev, [row.id]: { ...d, _saving: true } }));
    try {
      const payload: Record<string, unknown> = {};
      if (d.label_es !== undefined && d.label_es !== row.label_es) payload.label_es = d.label_es;
      if (d.label_en !== undefined && d.label_en !== row.label_en) payload.label_en = d.label_en;
      if (d.category !== undefined && d.category !== row.category) payload.category = d.category;
      if (d.sort_order !== undefined && d.sort_order !== row.sort_order)
        payload.sort_order = d.sort_order;
      if (Object.keys(payload).length === 0) {
        setDraft((prev) => {
          const next = { ...prev };
          delete next[row.id];
          return next;
        });
        return;
      }
      const updated = await catalogMetaApi.updateLabel(row.id, payload);
      setRows((prev) => prev.map((r) => (r.id === row.id ? updated : r)));
      setDraft((prev) => {
        const next = { ...prev };
        delete next[row.id];
        return next;
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error guardando");
      setDraft((prev) => ({ ...prev, [row.id]: { ...d, _saving: false } }));
    }
  };

  const remove = async (row: LabelItem) => {
    if (!confirm(`¿Eliminar etiqueta ${row.code}?`)) return;
    try {
      await catalogMetaApi.deleteLabel(row.id);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error eliminando");
    }
  };

  const createNew = async () => {
    if (!creating) return;
    try {
      await catalogMetaApi.createLabel({
        code: creating.code.trim(),
        label_es: creating.label_es.trim(),
        label_en: creating.label_en || null,
        category: creating.category || null,
        sort_order: creating.sort_order ?? 0,
      });
      setCreating(null);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error creando");
    }
  };

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput.trim());
    setPage(1);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <form onSubmit={submitSearch} style={{ display: "flex", gap: 6 }}>
          <input
            type="text"
            value={searchInput}
            placeholder="Buscar por código o etiqueta…"
            onChange={(e) => setSearchInput(e.target.value)}
            style={{ ...fieldStyle, minWidth: 260 }}
          />
          <Button type="submit" disabled={loading}>Buscar</Button>
          {search ? (
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setSearchInput("");
                setSearch("");
                setPage(1);
              }}
            >
              ✕
            </Button>
          ) : null}
        </form>

        <label style={{ fontSize: 13, display: "inline-flex", alignItems: "center", gap: 6 }}>
          Categoría:
          <select
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              setPage(1);
            }}
            style={fieldStyle}
          >
            <option value="">(todas)</option>
            {categories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>

        <Button
          onClick={() =>
            setCreating({ code: "", label_es: "", label_en: "", category: category || "", sort_order: 0 })
          }
        >
          + Agregar etiqueta
        </Button>
        <div style={{ flex: 1 }} />
        <small style={{ opacity: 0.75 }}>
          {total.toLocaleString("es-CO")} {total === 1 ? "etiqueta" : "etiquetas"}
        </small>
      </div>

      {error ? (
        <div
          role="alert"
          style={{
            padding: "8px 12px",
            background: "rgba(255,90,90,0.08)",
            border: "1px solid rgba(255,90,90,0.3)",
            borderRadius: 6,
            fontSize: 13,
            color: "rgba(255,180,180,0.95)",
          }}
        >
          {error}
        </div>
      ) : null}

      {creating ? (
        <CreateRow
          draft={creating}
          onChange={setCreating}
          onSave={createNew}
          onCancel={() => setCreating(null)}
          categories={categories}
        />
      ) : null}

      <div style={{ border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead style={{ background: "rgba(255,255,255,0.03)" }}>
            <tr>
              <Th style={{ width: 220 }}>Código</Th>
              <Th>Etiqueta (ES)</Th>
              <Th>Etiqueta (EN)</Th>
              <Th style={{ width: 140 }}>Categoría</Th>
              <Th style={{ width: 80 }}>Orden</Th>
              <Th style={{ width: 160 }}>Acciones</Th>
            </tr>
          </thead>
          <tbody>
            {loading && rows.length === 0 ? (
              <tr><Td colSpan={6} style={{ padding: 18, opacity: 0.7 }}>Cargando…</Td></tr>
            ) : rows.length === 0 ? (
              <tr><Td colSpan={6} style={{ padding: 18, opacity: 0.7 }}>Sin resultados.</Td></tr>
            ) : (
              rows.map((row) => {
                const d = draft[row.id] ?? {};
                const dirty =
                  d.label_es !== undefined ||
                  d.label_en !== undefined ||
                  d.category !== undefined ||
                  d.sort_order !== undefined;
                return (
                  <tr key={row.id} style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}>
                    <Td><code style={{ fontSize: 12 }}>{row.code}</code></Td>
                    <Td>
                      <input
                        type="text"
                        value={d.label_es ?? row.label_es}
                        onChange={(e) => setField(row.id, { label_es: e.target.value })}
                        style={{ ...fieldStyle, width: "100%" }}
                      />
                    </Td>
                    <Td>
                      <input
                        type="text"
                        value={d.label_en ?? row.label_en ?? ""}
                        placeholder="—"
                        onChange={(e) => setField(row.id, { label_en: e.target.value || null })}
                        style={{ ...fieldStyle, width: "100%" }}
                      />
                    </Td>
                    <Td>
                      <input
                        type="text"
                        list={`cats-${row.id}`}
                        value={d.category ?? row.category ?? ""}
                        placeholder="—"
                        onChange={(e) => setField(row.id, { category: e.target.value || null })}
                        style={{ ...fieldStyle, width: "100%" }}
                      />
                      <datalist id={`cats-${row.id}`}>
                        {categories.map((c) => <option key={c} value={c} />)}
                      </datalist>
                    </Td>
                    <Td>
                      <input
                        type="number"
                        value={d.sort_order ?? row.sort_order}
                        onChange={(e) => setField(row.id, { sort_order: Number(e.target.value) })}
                        style={{ ...fieldStyle, width: 70 }}
                      />
                    </Td>
                    <Td>
                      <div style={{ display: "flex", gap: 6 }}>
                        <Button
                          onClick={() => save(row)}
                          disabled={!dirty || d._saving}
                        >
                          {d._saving ? "…" : "Guardar"}
                        </Button>
                        <Button variant="ghost" onClick={() => remove(row)}>Eliminar</Button>
                      </div>
                    </Td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <div
        style={{
          display: "flex",
          gap: 10,
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
        }}
      >
        <small style={{ opacity: 0.75 }}>
          Página {page} de {totalPages}
        </small>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <label style={{ fontSize: 12 }}>
            Por página:
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              style={{ ...fieldStyle, marginLeft: 6 }}
            >
              {PAGE_SIZES.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <Button variant="ghost" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1 || loading}>←</Button>
          <Button variant="ghost" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages || loading}>→</Button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------

type CreateDraft = {
  code: string;
  label_es: string;
  label_en?: string;
  category?: string;
  sort_order?: number;
};

function CreateRow({
  draft,
  onChange,
  onSave,
  onCancel,
  categories,
}: {
  draft: CreateDraft;
  onChange: (next: CreateDraft) => void;
  onSave: () => void;
  onCancel: () => void;
  categories: string[];
}) {
  return (
    <div
      style={{
        border: "1px solid rgba(80,140,255,0.4)",
        background: "rgba(80,140,255,0.06)",
        borderRadius: 10,
        padding: 10,
        display: "flex",
        flexWrap: "wrap",
        gap: 8,
        alignItems: "center",
      }}
    >
      <input
        type="text"
        placeholder="Código"
        value={draft.code}
        onChange={(e) => onChange({ ...draft, code: e.target.value })}
        style={{ ...fieldStyle, minWidth: 160 }}
      />
      <input
        type="text"
        placeholder="Etiqueta ES"
        value={draft.label_es}
        onChange={(e) => onChange({ ...draft, label_es: e.target.value })}
        style={{ ...fieldStyle, flex: 1, minWidth: 200 }}
      />
      <input
        type="text"
        placeholder="Etiqueta EN (opcional)"
        value={draft.label_en ?? ""}
        onChange={(e) => onChange({ ...draft, label_en: e.target.value })}
        style={{ ...fieldStyle, flex: 1, minWidth: 200 }}
      />
      <input
        type="text"
        list="new-label-cats"
        placeholder="Categoría"
        value={draft.category ?? ""}
        onChange={(e) => onChange({ ...draft, category: e.target.value })}
        style={{ ...fieldStyle, width: 160 }}
      />
      <datalist id="new-label-cats">
        {categories.map((c) => <option key={c} value={c} />)}
      </datalist>
      <input
        type="number"
        value={draft.sort_order ?? 0}
        onChange={(e) => onChange({ ...draft, sort_order: Number(e.target.value) })}
        style={{ ...fieldStyle, width: 70 }}
      />
      <Button onClick={onSave} disabled={!draft.code.trim() || !draft.label_es.trim()}>Crear</Button>
      <Button variant="ghost" onClick={onCancel}>Cancelar</Button>
    </div>
  );
}

// ---------------------------------------------------------------------------

function Th({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <th
      style={{
        textAlign: "left",
        fontSize: 12,
        padding: "8px 10px",
        color: "var(--muted)",
        fontWeight: 500,
        ...style,
      }}
    >
      {children}
    </th>
  );
}

function Td({ children, style, colSpan }: { children: React.ReactNode; style?: React.CSSProperties; colSpan?: number }) {
  return (
    <td style={{ padding: "6px 10px", fontSize: 13, ...style }} colSpan={colSpan}>
      {children}
    </td>
  );
}

const fieldStyle: React.CSSProperties = {
  background: "transparent",
  color: "inherit",
  border: "1px solid rgba(255,255,255,0.12)",
  borderRadius: 4,
  padding: "4px 8px",
  fontSize: 13,
};
