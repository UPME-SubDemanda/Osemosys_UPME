/**
 * UnitsTab — unidades base + conversiones por variable (Fase 3.3.E).
 *
 * Cada variable tiene una ``unit_base`` y un array de ``display_units`` con
 * factor de conversión. Se edita como JSON estructurado (tabla de filas).
 */
import { useCallback, useEffect, useState } from "react";
import {
  catalogMetaUnitApi,
  type VariableUnitItem,
  type DisplayUnitEntry,
} from "@/features/catalogMeta/api/catalogMetaApi";
import { Button } from "@/shared/components/Button";

export function UnitsTab() {
  const [rows, setRows] = useState<VariableUnitItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState<NewDraft | null>(null);
  const [drafts, setDrafts] = useState<Record<number, EditDraft>>({});

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await catalogMetaUnitApi.list();
      setRows(resp.items);
      setDrafts({});
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const patchDraft = (id: number, patch: Partial<EditDraft>) =>
    setDrafts((prev) => ({ ...prev, [id]: { ...(prev[id] ?? {}), ...patch } }));

  const save = async (row: VariableUnitItem) => {
    const d = drafts[row.id];
    if (!d) return;
    try {
      const patch: { unit_base?: string; display_units_json?: DisplayUnitEntry[] } = {};
      if (d.unit_base !== undefined) patch.unit_base = d.unit_base;
      if (d.display_units !== undefined) patch.display_units_json = d.display_units;
      await catalogMetaUnitApi.update(row.id, patch);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    }
  };

  const remove = async (row: VariableUnitItem) => {
    if (!confirm(`¿Eliminar unidad para ${row.variable_name}?`)) return;
    try {
      await catalogMetaUnitApi.delete(row.id);
      setRows((prev) => prev.filter((r) => r.id !== row.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    }
  };

  const createNew = async () => {
    if (!creating) return;
    try {
      await catalogMetaUnitApi.create({
        variable_name: creating.variable_name.trim(),
        unit_base: creating.unit_base.trim(),
        display_units_json: creating.display_units,
      });
      setCreating(null);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <Button
          onClick={() =>
            setCreating({
              variable_name: "",
              unit_base: "",
              display_units: [{ code: "", label: "", factor: 1 }],
            })
          }
        >
          + Nueva unidad
        </Button>
        <Button variant="ghost" onClick={reload} disabled={loading}>
          {loading ? "Cargando…" : "Recargar"}
        </Button>
        <div style={{ flex: 1 }} />
        <small style={{ opacity: 0.7 }}>{rows.length} unidades definidas</small>
      </div>

      {error ? <ErrorBox>{error}</ErrorBox> : null}

      {creating ? (
        <div style={cardStyle(true)}>
          <div style={headerRowStyle}>
            <input
              type="text"
              placeholder="variable_name (ej. __DEFAULT_ENERGY__)"
              value={creating.variable_name}
              onChange={(e) => setCreating({ ...creating, variable_name: e.target.value })}
              style={{ ...fieldStyle, flex: 1 }}
            />
            <input
              type="text"
              placeholder="Unidad base (PJ)"
              value={creating.unit_base}
              onChange={(e) => setCreating({ ...creating, unit_base: e.target.value })}
              style={{ ...fieldStyle, width: 120 }}
            />
            <Button onClick={createNew} disabled={!creating.variable_name.trim() || !creating.unit_base.trim()}>
              Crear
            </Button>
            <Button variant="ghost" onClick={() => setCreating(null)}>
              ✕
            </Button>
          </div>
          <DisplayUnitsEditor
            units={creating.display_units ?? []}
            onChange={(units) => setCreating({ ...creating, display_units: units })}
          />
        </div>
      ) : null}

      {rows.length === 0 && !loading ? (
        <div style={{ opacity: 0.6, fontStyle: "italic", padding: 12 }}>
          Sin unidades definidas.
        </div>
      ) : null}

      {rows.map((row) => {
        const d = drafts[row.id] ?? {};
        const currentUnitBase = d.unit_base ?? row.unit_base;
        const currentUnits = d.display_units ?? row.display_units_json ?? [];
        const dirty = d.unit_base !== undefined || d.display_units !== undefined;
        return (
          <div key={row.id} style={cardStyle(false)}>
            <div style={headerRowStyle}>
              <code style={{ fontWeight: 600 }}>{row.variable_name}</code>
              <span style={{ opacity: 0.5, fontSize: 11 }}>base:</span>
              <input
                type="text"
                value={currentUnitBase}
                onChange={(e) => patchDraft(row.id, { unit_base: e.target.value })}
                style={{ ...fieldStyle, width: 120 }}
              />
              <div style={{ flex: 1 }} />
              <Button onClick={() => save(row)} disabled={!dirty}>
                Guardar
              </Button>
              <Button variant="ghost" onClick={() => remove(row)}>
                🗑
              </Button>
            </div>
            <DisplayUnitsEditor
              units={currentUnits}
              onChange={(units) => patchDraft(row.id, { display_units: units })}
            />
          </div>
        );
      })}
    </div>
  );
}

function DisplayUnitsEditor({
  units,
  onChange,
}: {
  units: DisplayUnitEntry[];
  onChange: (next: DisplayUnitEntry[]) => void;
}) {
  const setAt = (idx: number, patch: Partial<DisplayUnitEntry>) => {
    const next = units.map((u, i) => (i === idx ? { ...u, ...patch } : u));
    onChange(next);
  };
  return (
    <div style={{ marginTop: 8 }}>
      <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ opacity: 0.65, textAlign: "left" }}>
            <th style={{ padding: "2px 6px", width: 120 }}>Código</th>
            <th style={{ padding: "2px 6px" }}>Label</th>
            <th style={{ padding: "2px 6px", width: 180 }}>Factor (base × factor = display)</th>
            <th style={{ padding: "2px 6px", width: 36 }} />
          </tr>
        </thead>
        <tbody>
          {units.map((u, i) => (
            <tr key={i}>
              <td style={{ padding: "2px 6px" }}>
                <input
                  type="text"
                  value={u.code}
                  onChange={(e) => setAt(i, { code: e.target.value })}
                  style={{ ...fieldStyle, width: "100%" }}
                />
              </td>
              <td style={{ padding: "2px 6px" }}>
                <input
                  type="text"
                  value={u.label}
                  onChange={(e) => setAt(i, { label: e.target.value })}
                  style={{ ...fieldStyle, width: "100%" }}
                />
              </td>
              <td style={{ padding: "2px 6px" }}>
                <input
                  type="number"
                  step="any"
                  value={u.factor}
                  onChange={(e) => setAt(i, { factor: Number(e.target.value) })}
                  style={{ ...fieldStyle, width: "100%" }}
                />
              </td>
              <td style={{ padding: "2px 6px", textAlign: "center" }}>
                <button
                  type="button"
                  onClick={() => onChange(units.filter((_, k) => k !== i))}
                  style={iconBtnStyle}
                  title="Quitar"
                >
                  ✕
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Button
        variant="ghost"
        onClick={() => onChange([...units, { code: "", label: "", factor: 1 }])}
      >
        + Fila
      </Button>
    </div>
  );
}

type NewDraft = {
  variable_name: string;
  unit_base: string;
  display_units: DisplayUnitEntry[];
};

type EditDraft = {
  unit_base?: string;
  display_units?: DisplayUnitEntry[];
};

function ErrorBox({ children }: { children: React.ReactNode }) {
  return (
    <div
      role="alert"
      style={{
        padding: "6px 10px",
        background: "rgba(255,90,90,0.08)",
        border: "1px solid rgba(255,90,90,0.3)",
        borderRadius: 6,
        fontSize: 12,
        color: "rgba(255,180,180,0.95)",
      }}
    >
      {children}
    </div>
  );
}

const fieldStyle: React.CSSProperties = {
  background: "transparent",
  color: "inherit",
  border: "1px solid rgba(255,255,255,0.12)",
  borderRadius: 4,
  padding: "3px 6px",
  fontSize: 12,
};

const iconBtnStyle: React.CSSProperties = {
  background: "transparent",
  border: "none",
  color: "inherit",
  cursor: "pointer",
  opacity: 0.6,
  fontSize: 12,
};

const cardStyle = (creating: boolean): React.CSSProperties => ({
  border: creating ? "1px solid rgba(80,140,255,0.4)" : "1px solid rgba(255,255,255,0.1)",
  background: creating ? "rgba(80,140,255,0.06)" : "rgba(255,255,255,0.02)",
  borderRadius: 10,
  padding: 10,
});

const headerRowStyle: React.CSSProperties = {
  display: "flex",
  gap: 8,
  alignItems: "center",
  flexWrap: "wrap",
};
