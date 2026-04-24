/**
 * ColorsTab — administración de la paleta de colores (Fase 3.3.A).
 *
 * Tabla editable agrupada por `group` (fuel/pwr/sector/emission/family).
 * Edición inline: color con <input type="color"> + descripción + orden.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  catalogMetaApi,
  catalogMetaAuditApi,
  ALLOWED_COLOR_GROUPS,
  type ColorGroup,
  type ColorItem,
} from "@/features/catalogMeta/api/catalogMetaApi";
import { Button } from "@/shared/components/Button";

const GROUP_LABELS: Record<ColorGroup, string> = {
  fuel: "Combustible",
  pwr: "Electricidad (PWR)",
  sector: "Sector",
  emission: "Emisión",
  family: "Familia tech",
};

type DraftRow = Partial<ColorItem> & { _new?: boolean; _saving?: boolean };

export function ColorsTab() {
  const [groupFilter, setGroupFilter] = useState<ColorGroup | "all">("fuel");
  const [rows, setRows] = useState<ColorItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<number, DraftRow>>({});
  const [creating, setCreating] = useState<ColorCreateDraft | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await catalogMetaApi.listColors(
        groupFilter === "all" ? undefined : (groupFilter as ColorGroup),
      );
      setRows(resp.items);
      setDraft({});
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error cargando colores");
    } finally {
      setLoading(false);
    }
  }, [groupFilter]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const grouped = useMemo(() => {
    const out: Record<string, ColorItem[]> = {};
    for (const r of rows) {
      (out[r.group] ||= []).push(r);
    }
    return out;
  }, [rows]);

  const setField = (id: number, patch: Partial<ColorItem>) =>
    setDraft((prev) => ({ ...prev, [id]: { ...(prev[id] ?? {}), ...patch } }));

  const save = async (row: ColorItem) => {
    const d = draft[row.id];
    if (!d) return;
    setDraft((prev) => ({ ...prev, [row.id]: { ...d, _saving: true } }));
    try {
      const payload: Record<string, unknown> = {};
      if (d.color_hex !== undefined && d.color_hex !== row.color_hex)
        payload.color_hex = d.color_hex;
      if (d.description !== undefined && d.description !== row.description)
        payload.description = d.description;
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
      const updated = await catalogMetaApi.updateColor(row.id, payload);
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

  const remove = async (row: ColorItem) => {
    if (!confirm(`¿Eliminar color ${row.group}/${row.key}?`)) return;
    try {
      await catalogMetaApi.deleteColor(row.id);
      setRows((prev) => prev.filter((r) => r.id !== row.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error eliminando");
    }
  };

  const createNew = async () => {
    if (!creating) return;
    try {
      const created = await catalogMetaApi.createColor({
        key: creating.key.trim(),
        group: creating.group,
        color_hex: creating.color_hex,
        description: creating.description || null,
        sort_order: creating.sort_order ?? 0,
      });
      setRows((prev) => [...prev, created]);
      setCreating(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error creando");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <label style={{ fontSize: 13, display: "inline-flex", alignItems: "center", gap: 6 }}>
          Grupo:
          <select
            value={groupFilter}
            onChange={(e) => setGroupFilter(e.target.value as ColorGroup | "all")}
            style={{
              background: "transparent",
              color: "inherit",
              border: "1px solid rgba(255,255,255,0.12)",
              borderRadius: 4,
              padding: "4px 8px",
            }}
          >
            <option value="all">Todos</option>
            {ALLOWED_COLOR_GROUPS.map((g) => (
              <option key={g} value={g}>
                {GROUP_LABELS[g]}
              </option>
            ))}
          </select>
        </label>
        <Button onClick={reload} disabled={loading} variant="ghost">
          {loading ? "Cargando…" : "Recargar"}
        </Button>
        <Button
          onClick={() =>
            setCreating({
              key: "",
              group: groupFilter === "all" ? "fuel" : (groupFilter as ColorGroup),
              color_hex: "#888888",
              description: "",
              sort_order: rows.length,
            })
          }
        >
          + Agregar color
        </Button>
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
          forceGroup={groupFilter === "all" ? undefined : (groupFilter as ColorGroup)}
        />
      ) : null}

      {Object.entries(grouped).map(([group, items]) => (
        <div
          key={group}
          style={{ border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10 }}
        >
          <div
            style={{
              padding: "8px 12px",
              borderBottom: "1px solid rgba(255,255,255,0.08)",
              background: "rgba(255,255,255,0.03)",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {GROUP_LABELS[group as ColorGroup] ?? group} ({items.length})
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead style={{ background: "rgba(255,255,255,0.02)" }}>
              <tr>
                <Th>Clave</Th>
                <Th style={{ width: 90 }}>Color</Th>
                <Th>Descripción</Th>
                <Th style={{ width: 80 }}>Orden</Th>
                <Th style={{ width: 160 }}>Acciones</Th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => {
                const d = draft[row.id] ?? {};
                const currentHex = d.color_hex ?? row.color_hex;
                const currentDesc = d.description ?? row.description ?? "";
                const currentOrder = d.sort_order ?? row.sort_order;
                const dirty =
                  d.color_hex !== undefined ||
                  d.description !== undefined ||
                  d.sort_order !== undefined;
                return (
                  <tr
                    key={row.id}
                    style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}
                  >
                    <Td>
                      <code style={{ fontSize: 13 }}>{row.key}</code>
                    </Td>
                    <Td>
                      <HexColorField
                        value={currentHex}
                        onChange={(next) => setField(row.id, { color_hex: next })}
                        rowId={row.id}
                      />
                    </Td>
                    <Td>
                      <input
                        type="text"
                        value={currentDesc}
                        placeholder="—"
                        onChange={(e) => setField(row.id, { description: e.target.value })}
                        style={fieldStyle}
                      />
                    </Td>
                    <Td>
                      <input
                        type="number"
                        value={currentOrder}
                        onChange={(e) => setField(row.id, { sort_order: Number(e.target.value) })}
                        style={{ ...fieldStyle, width: 70 }}
                      />
                    </Td>
                    <Td>
                      <div style={{ display: "flex", gap: 6 }}>
                        <Button
                          onClick={() => save(row)}
                          disabled={!dirty || d._saving}
                          variant="primary"
                        >
                          {d._saving ? "…" : "Guardar"}
                        </Button>
                        <Button onClick={() => remove(row)} variant="ghost">
                          Eliminar
                        </Button>
                      </div>
                    </Td>
                  </tr>
                );
              })}
              {items.length === 0 ? (
                <tr>
                  <Td colSpan={5} style={{ opacity: 0.65, textAlign: "center", padding: 16 }}>
                    Sin entradas.
                  </Td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------

type ColorCreateDraft = {
  key: string;
  group: ColorGroup;
  color_hex: string;
  description?: string;
  sort_order?: number;
};

function CreateRow({
  draft,
  onChange,
  onSave,
  onCancel,
  forceGroup,
}: {
  draft: ColorCreateDraft;
  onChange: (next: ColorCreateDraft) => void;
  onSave: () => void;
  onCancel: () => void;
  forceGroup?: ColorGroup | undefined;
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
      <label>
        Grupo:
        <select
          value={draft.group}
          disabled={!!forceGroup}
          onChange={(e) => onChange({ ...draft, group: e.target.value as ColorGroup })}
          style={{ ...fieldStyle, marginLeft: 6 }}
        >
          {ALLOWED_COLOR_GROUPS.map((g) => (
            <option key={g} value={g}>
              {GROUP_LABELS[g]}
            </option>
          ))}
        </select>
      </label>
      <input
        type="text"
        placeholder="Clave (ej. NGS)"
        value={draft.key}
        onChange={(e) => onChange({ ...draft, key: e.target.value })}
        style={{ ...fieldStyle, minWidth: 140 }}
      />
      <HexColorField
        value={draft.color_hex}
        onChange={(next) => onChange({ ...draft, color_hex: next })}
      />
      <input
        type="text"
        placeholder="Descripción"
        value={draft.description ?? ""}
        onChange={(e) => onChange({ ...draft, description: e.target.value })}
        style={{ ...fieldStyle, flex: 1, minWidth: 200 }}
      />
      <input
        type="number"
        value={draft.sort_order ?? 0}
        onChange={(e) => onChange({ ...draft, sort_order: Number(e.target.value) })}
        style={{ ...fieldStyle, width: 70 }}
      />
      <Button onClick={onSave} disabled={!draft.key.trim()}>
        Crear
      </Button>
      <Button variant="ghost" onClick={onCancel}>
        Cancelar
      </Button>
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

function Td({
  children,
  style,
  colSpan,
}: {
  children: React.ReactNode;
  style?: React.CSSProperties;
  colSpan?: number;
}) {
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

/** Convierte #RRGGBBAA → #RRGGBB para <input type="color"> (no soporta alpha). */
function toColorInputValue(hex: string): string {
  if (!hex) return "#000000";
  if (hex.length === 7) return hex;
  if (hex.length === 9) return hex.slice(0, 7);
  if (hex.length === 4) {
    // #rgb → #rrggbb
    return `#${hex[1]}${hex[1]}${hex[2]}${hex[2]}${hex[3]}${hex[3]}`;
  }
  return "#000000";
}

/** Regex idéntico al del backend — valida #RGB / #RRGGBB / #RRGGBBAA. */
const HEX_RE = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/;

/**
 * Picker nativo + text input + historial por fila para editar colores.
 * - Usuario puede pegar `#b27d00` en el text input.
 * - Botón ⟳ abre un popover con los colores previos de esa fila (desde
 *   ``catalog_meta_audit``). Click en uno → restaurar.
 */
function HexColorField({
  value,
  onChange,
  rowId,
}: {
  value: string;
  onChange: (next: string) => void;
  rowId?: number;
}) {
  const [text, setText] = useState(value);
  useEffect(() => {
    setText(value);
  }, [value]);
  const isValid = HEX_RE.test(text);

  const btnRef = useRef<HTMLButtonElement | null>(null);
  const popRef = useRef<HTMLDivElement | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const [history, setHistory] = useState<
    { color_hex: string; changed_at: string; username: string | null }[]
  >([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const loadHistory = useCallback(async () => {
    if (!rowId) return;
    setHistoryLoading(true);
    try {
      const resp = await catalogMetaAuditApi.list({
        table_name: "catalog_meta_color_palette",
        row_id: rowId,
        limit: 200,
      });
      // Extraer colores únicos de los eventos (before + after), en orden desc.
      const seen = new Set<string>();
      const out: typeof history = [];
      for (const ev of resp.items) {
        const diff = ev.diff_json as
          | { before?: Record<string, unknown>; after?: Record<string, unknown> }
          | null;
        const cands: string[] = [];
        if (diff?.after && typeof diff.after.color_hex === "string")
          cands.push(diff.after.color_hex);
        if (diff?.before && typeof diff.before.color_hex === "string")
          cands.push(diff.before.color_hex);
        for (const hex of cands) {
          if (!seen.has(hex) && HEX_RE.test(hex)) {
            seen.add(hex);
            out.push({
              color_hex: hex,
              changed_at: ev.changed_at,
              username: ev.changed_by_username,
            });
          }
        }
      }
      setHistory(out);
    } catch {
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }, [rowId]);

  const toggleHistory = () => {
    if (!rowId) return;
    if (historyOpen) {
      setHistoryOpen(false);
      return;
    }
    const rect = btnRef.current?.getBoundingClientRect();
    if (rect) {
      setPos({ top: rect.bottom + 4, left: Math.max(8, rect.left - 80) });
    }
    setHistoryOpen(true);
    void loadHistory();
  };

  useEffect(() => {
    if (!historyOpen) return;
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node;
      if (btnRef.current?.contains(t)) return;
      if (popRef.current?.contains(t)) return;
      setHistoryOpen(false);
    };
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setHistoryOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onEsc);
    };
  }, [historyOpen]);

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <input
        type="color"
        value={toColorInputValue(value)}
        onChange={(e) => onChange(e.target.value.toLowerCase())}
        style={{
          width: 28,
          height: 24,
          padding: 0,
          border: "1px solid rgba(255,255,255,0.12)",
          background: "transparent",
          cursor: "pointer",
        }}
        aria-label="Seleccionar color"
      />
      <input
        type="text"
        value={text}
        placeholder="#rrggbb"
        spellCheck={false}
        onChange={(e) => setText(e.target.value.trim())}
        onBlur={() => {
          if (isValid) onChange(text.toLowerCase());
          else setText(value);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && isValid) {
            onChange(text.toLowerCase());
            (e.target as HTMLInputElement).blur();
          } else if (e.key === "Escape") {
            setText(value);
            (e.target as HTMLInputElement).blur();
          }
        }}
        style={{
          ...fieldStyle,
          width: 92,
          fontFamily: "var(--font-mono, monospace)",
          fontSize: 12,
          borderColor: isValid
            ? "rgba(255,255,255,0.12)"
            : "rgba(255,90,90,0.55)",
        }}
        title={isValid ? "Enter o salir para aplicar" : "Formato inválido"}
      />
      {rowId ? (
        <button
          ref={btnRef}
          type="button"
          onClick={toggleHistory}
          title="Historial de este color"
          style={{
            width: 24,
            height: 24,
            padding: 0,
            border: "1px solid rgba(255,255,255,0.12)",
            background: "transparent",
            color: "var(--muted)",
            borderRadius: 4,
            cursor: "pointer",
            fontSize: 12,
            lineHeight: 1,
          }}
          aria-label="Historial"
        >
          ⟳
        </button>
      ) : null}
      {historyOpen && pos
        ? createPortal(
            <div
              ref={popRef}
              role="dialog"
              aria-label="Historial de colores"
              style={{
                position: "fixed",
                top: pos.top,
                left: pos.left,
                width: 240,
                maxHeight: 320,
                overflowY: "auto",
                background: "rgba(18, 20, 26, 0.98)",
                border: "1px solid rgba(255,255,255,0.14)",
                borderRadius: 8,
                boxShadow: "0 12px 40px rgba(0,0,0,0.5)",
                padding: 8,
                zIndex: 10000,
                fontSize: 12,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  paddingBottom: 6,
                  borderBottom: "1px solid rgba(255,255,255,0.08)",
                  marginBottom: 6,
                }}
              >
                <strong style={{ fontSize: 12 }}>Historial</strong>
                <button
                  type="button"
                  onClick={() => setHistoryOpen(false)}
                  style={{
                    background: "transparent",
                    border: "none",
                    color: "var(--muted)",
                    cursor: "pointer",
                    fontSize: 14,
                    padding: 0,
                  }}
                  aria-label="Cerrar"
                >
                  ✕
                </button>
              </div>
              {historyLoading ? (
                <div style={{ opacity: 0.7, padding: 6 }}>Cargando…</div>
              ) : history.length === 0 ? (
                <div style={{ opacity: 0.7, padding: 6 }}>
                  Sin historial previo para este color.
                </div>
              ) : (
                <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
                  {history.map((h, i) => {
                    const isCurrent = h.color_hex.toLowerCase() === value.toLowerCase();
                    return (
                      <li key={i}>
                        <button
                          type="button"
                          disabled={isCurrent}
                          onClick={() => {
                            onChange(h.color_hex.toLowerCase());
                            setHistoryOpen(false);
                          }}
                          style={{
                            width: "100%",
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                            background: "transparent",
                            border: "none",
                            color: "inherit",
                            padding: "5px 4px",
                            cursor: isCurrent ? "default" : "pointer",
                            textAlign: "left",
                            fontSize: 12,
                            opacity: isCurrent ? 0.55 : 1,
                          }}
                          title={isCurrent ? "Color actual" : "Restaurar este color"}
                        >
                          <span
                            style={{
                              width: 18,
                              height: 18,
                              borderRadius: 3,
                              background: h.color_hex,
                              border: "1px solid rgba(255,255,255,0.2)",
                              flexShrink: 0,
                            }}
                          />
                          <code style={{ fontSize: 11 }}>{h.color_hex}</code>
                          <span style={{ flex: 1 }} />
                          <small style={{ opacity: 0.6, fontSize: 10 }}>
                            {new Date(h.changed_at).toLocaleString("es-CO", {
                              dateStyle: "short",
                              timeStyle: "short",
                            })}
                          </small>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>,
            document.body,
          )
        : null}
    </span>
  );
}
