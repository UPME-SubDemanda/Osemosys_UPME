/**
 * ModulesTab — Jerarquía del selector de gráficas (Fase 3.3.D).
 *
 *  - Módulos (nivel 1): Sector Eléctrico, Demanda, etc.
 *  - Submódulos (nivel 2): subsectores bajo Demanda, etc.
 *  - Reordenar con ▲▼, editar label/icono/visibilidad, crear, eliminar.
 */
import { useCallback, useEffect, useState } from "react";
import {
  catalogMetaModuleApi,
  type ChartModuleItem,
  type ChartSubmoduleItem,
} from "@/features/catalogMeta/api/catalogMetaApi";
import { Button } from "@/shared/components/Button";

export function ModulesTab() {
  const [tree, setTree] = useState<ChartModuleItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newModule, setNewModule] = useState<NewModuleDraft | null>(null);
  const [newSubFor, setNewSubFor] = useState<number | null>(null);
  const [newSubDraft, setNewSubDraft] = useState<NewSubDraft>({ code: "", label: "", icon: "" });

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await catalogMetaModuleApi.tree();
      setTree(resp.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  // ------------------------------------------------------------------
  //  Módulos
  // ------------------------------------------------------------------

  const updateModule = async (m: ChartModuleItem, patch: Partial<ChartModuleItem>) => {
    try {
      await catalogMetaModuleApi.updateModule(m.id, patch);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    }
  };

  const removeModule = async (m: ChartModuleItem) => {
    if (m.chart_count > 0) {
      alert(`El módulo "${m.label}" tiene ${m.chart_count} gráfica(s). Reasígnalas primero.`);
      return;
    }
    if (!confirm(`¿Eliminar módulo "${m.label}"? También se eliminarán sus ${m.submodules.length} submódulo(s).`)) return;
    try {
      await catalogMetaModuleApi.deleteModule(m.id);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    }
  };

  const moveModule = async (m: ChartModuleItem, dir: -1 | 1) => {
    const idx = tree.findIndex((x) => x.id === m.id);
    const swap = tree[idx + dir];
    if (!swap) return;
    try {
      await Promise.all([
        catalogMetaModuleApi.updateModule(m.id, { sort_order: swap.sort_order }),
        catalogMetaModuleApi.updateModule(swap.id, { sort_order: m.sort_order }),
      ]);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error reordenando");
    }
  };

  const createModule = async () => {
    if (!newModule) return;
    try {
      await catalogMetaModuleApi.createModule({
        code: newModule.code.trim(),
        label: newModule.label.trim(),
        icon: newModule.icon || null,
        sort_order: tree.length,
        is_visible: true,
      });
      setNewModule(null);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error creando");
    }
  };

  // ------------------------------------------------------------------
  //  Submódulos
  // ------------------------------------------------------------------

  const updateSub = async (s: ChartSubmoduleItem, patch: Partial<ChartSubmoduleItem>) => {
    try {
      await catalogMetaModuleApi.updateSubmodule(s.id, patch);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    }
  };

  const removeSub = async (s: ChartSubmoduleItem) => {
    if (!confirm(`¿Eliminar submódulo "${s.label}"? Las gráficas quedarán sin submódulo.`)) return;
    try {
      await catalogMetaModuleApi.deleteSubmodule(s.id);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    }
  };

  const moveSub = async (parent: ChartModuleItem, s: ChartSubmoduleItem, dir: -1 | 1) => {
    const idx = parent.submodules.findIndex((x) => x.id === s.id);
    const swap = parent.submodules[idx + dir];
    if (!swap) return;
    try {
      await Promise.all([
        catalogMetaModuleApi.updateSubmodule(s.id, { sort_order: swap.sort_order }),
        catalogMetaModuleApi.updateSubmodule(swap.id, { sort_order: s.sort_order }),
      ]);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error reordenando");
    }
  };

  const createSub = async (module_id: number) => {
    if (!newSubDraft.code.trim() || !newSubDraft.label.trim()) return;
    try {
      await catalogMetaModuleApi.createSubmodule({
        module_id,
        code: newSubDraft.code.trim(),
        label: newSubDraft.label.trim(),
        icon: newSubDraft.icon || null,
        sort_order: tree.find((m) => m.id === module_id)?.submodules.length ?? 0,
        is_visible: true,
      });
      setNewSubFor(null);
      setNewSubDraft({ code: "", label: "", icon: "" });
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error creando");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <Button
          onClick={() =>
            setNewModule({ code: "", label: "", icon: "" })
          }
        >
          + Nuevo módulo
        </Button>
        <Button variant="ghost" onClick={reload} disabled={loading}>
          {loading ? "Cargando…" : "Recargar"}
        </Button>
        <div style={{ flex: 1 }} />
        <small style={{ opacity: 0.7 }}>
          {tree.length} módulos · {tree.reduce((a, m) => a + m.submodules.length, 0)} submódulos
        </small>
      </div>

      {error ? <ErrorBox>{error}</ErrorBox> : null}

      {newModule ? (
        <div style={createRowStyle}>
          <input
            type="text"
            placeholder="Código (electrico)"
            value={newModule.code}
            onChange={(e) => setNewModule({ ...newModule, code: e.target.value })}
            style={{ ...fieldStyle, width: 140 }}
          />
          <input
            type="text"
            placeholder="Label (Sector Eléctrico)"
            value={newModule.label}
            onChange={(e) => setNewModule({ ...newModule, label: e.target.value })}
            style={{ ...fieldStyle, flex: 1, minWidth: 200 }}
          />
          <input
            type="text"
            placeholder="Icono (emoji)"
            value={newModule.icon}
            onChange={(e) => setNewModule({ ...newModule, icon: e.target.value })}
            style={{ ...fieldStyle, width: 70 }}
          />
          <Button onClick={createModule} disabled={!newModule.code.trim() || !newModule.label.trim()}>
            Crear
          </Button>
          <Button variant="ghost" onClick={() => setNewModule(null)}>
            ✕
          </Button>
        </div>
      ) : null}

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {tree.map((m, idx) => (
          <div key={m.id} style={moduleCardStyle(m.is_visible)}>
            <div style={moduleHeaderStyle}>
              <span style={{ fontSize: 18 }}>{m.icon || "📁"}</span>
              <input
                type="text"
                value={m.label}
                onChange={(e) => updateModule(m, { label: e.target.value })}
                onBlur={(e) => updateModule(m, { label: e.target.value })}
                style={{ ...fieldStyle, flex: 1, fontWeight: 600 }}
              />
              <input
                type="text"
                value={m.icon ?? ""}
                placeholder="🔖"
                onChange={(e) => updateModule(m, { icon: e.target.value || null })}
                style={{ ...fieldStyle, width: 50, textAlign: "center" }}
                title="Icono emoji"
              />
              <code style={{ fontSize: 11, opacity: 0.5 }}>{m.code}</code>
              <span style={{ fontSize: 11, opacity: 0.6 }}>
                {m.chart_count} gráfica{m.chart_count === 1 ? "" : "s"}
              </span>
              <label style={{ fontSize: 11, display: "inline-flex", alignItems: "center", gap: 4 }}>
                <input
                  type="checkbox"
                  checked={m.is_visible}
                  onChange={(e) => updateModule(m, { is_visible: e.target.checked })}
                />
                Visible
              </label>
              <Button variant="ghost" onClick={() => moveModule(m, -1)} disabled={idx === 0}>
                ▲
              </Button>
              <Button variant="ghost" onClick={() => moveModule(m, 1)} disabled={idx === tree.length - 1}>
                ▼
              </Button>
              <Button variant="ghost" onClick={() => removeModule(m)}>
                🗑
              </Button>
            </div>

            <div style={{ paddingLeft: 24, marginTop: 6 }}>
              {m.submodules.length === 0 && newSubFor !== m.id ? (
                <small style={{ opacity: 0.55, fontStyle: "italic" }}>Sin submódulos.</small>
              ) : null}
              {m.submodules.map((s, sidx) => (
                <div key={s.id} style={submoduleRowStyle(s.is_visible)}>
                  <span style={{ fontSize: 14 }}>{s.icon || "▸"}</span>
                  <input
                    type="text"
                    value={s.label}
                    onChange={(e) => updateSub(s, { label: e.target.value })}
                    onBlur={(e) => updateSub(s, { label: e.target.value })}
                    style={{ ...fieldStyle, flex: 1 }}
                  />
                  <input
                    type="text"
                    value={s.icon ?? ""}
                    placeholder="▸"
                    onChange={(e) => updateSub(s, { icon: e.target.value || null })}
                    style={{ ...fieldStyle, width: 50, textAlign: "center" }}
                  />
                  <code style={{ fontSize: 11, opacity: 0.5 }}>{s.code}</code>
                  <label style={{ fontSize: 11, display: "inline-flex", alignItems: "center", gap: 4 }}>
                    <input
                      type="checkbox"
                      checked={s.is_visible}
                      onChange={(e) => updateSub(s, { is_visible: e.target.checked })}
                    />
                    Visible
                  </label>
                  <Button variant="ghost" onClick={() => moveSub(m, s, -1)} disabled={sidx === 0}>
                    ▲
                  </Button>
                  <Button variant="ghost" onClick={() => moveSub(m, s, 1)} disabled={sidx === m.submodules.length - 1}>
                    ▼
                  </Button>
                  <Button variant="ghost" onClick={() => removeSub(s)}>
                    🗑
                  </Button>
                </div>
              ))}

              {newSubFor === m.id ? (
                <div style={{ ...createRowStyle, marginTop: 6 }}>
                  <input
                    type="text"
                    placeholder="Código"
                    value={newSubDraft.code}
                    onChange={(e) => setNewSubDraft({ ...newSubDraft, code: e.target.value })}
                    style={{ ...fieldStyle, width: 140 }}
                  />
                  <input
                    type="text"
                    placeholder="Label"
                    value={newSubDraft.label}
                    onChange={(e) => setNewSubDraft({ ...newSubDraft, label: e.target.value })}
                    style={{ ...fieldStyle, flex: 1 }}
                  />
                  <input
                    type="text"
                    placeholder="Icono"
                    value={newSubDraft.icon}
                    onChange={(e) => setNewSubDraft({ ...newSubDraft, icon: e.target.value })}
                    style={{ ...fieldStyle, width: 60 }}
                  />
                  <Button onClick={() => createSub(m.id)}>Crear</Button>
                  <Button variant="ghost" onClick={() => setNewSubFor(null)}>
                    ✕
                  </Button>
                </div>
              ) : (
                <div style={{ marginTop: 6 }}>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setNewSubFor(m.id);
                      setNewSubDraft({ code: "", label: "", icon: "" });
                    }}
                  >
                    + Submódulo
                  </Button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------

type NewModuleDraft = { code: string; label: string; icon: string };
type NewSubDraft = { code: string; label: string; icon: string };

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
  padding: "3px 8px",
  fontSize: 13,
};

const createRowStyle: React.CSSProperties = {
  border: "1px solid rgba(80,140,255,0.4)",
  background: "rgba(80,140,255,0.06)",
  borderRadius: 8,
  padding: 8,
  display: "flex",
  gap: 6,
  alignItems: "center",
  flexWrap: "wrap",
};

const moduleCardStyle = (visible: boolean): React.CSSProperties => ({
  border: "1px solid rgba(255,255,255,0.1)",
  background: "rgba(255,255,255,0.02)",
  borderRadius: 10,
  padding: 10,
  opacity: visible ? 1 : 0.55,
});

const moduleHeaderStyle: React.CSSProperties = {
  display: "flex",
  gap: 8,
  alignItems: "center",
  flexWrap: "wrap",
};

const submoduleRowStyle = (visible: boolean): React.CSSProperties => ({
  display: "flex",
  gap: 6,
  alignItems: "center",
  flexWrap: "wrap",
  padding: "4px 0",
  borderTop: "1px dashed rgba(255,255,255,0.06)",
  opacity: visible ? 1 : 0.55,
});
