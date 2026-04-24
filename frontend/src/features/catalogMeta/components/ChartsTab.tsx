/**
 * ChartsTab — configuración completa de gráficas (Fase 3.3.F + 3.3.H).
 *
 * Lista de charts agrupados por módulo. Cada fila es editable inline
 * (label, variable, agrupación default, visible). Click "Detalles" abre
 * modal con todos los campos + sub-filtros.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  catalogMetaChartApi,
  catalogMetaModuleApi,
  type ChartConfigItem,
  type ChartSubfilterItem,
  type ChartModuleItem,
} from "@/features/catalogMeta/api/catalogMetaApi";
import { Button } from "@/shared/components/Button";
import { Modal } from "@/shared/components/Modal";

const AGRUPACIONES = ["TECNOLOGIA", "COMBUSTIBLE", "FUEL", "SECTOR", "YEAR", "EMISION"];
const COLOR_FNS = [
  "tecnologias",
  "electricidad",
  "grupo_fijo",
  "por_sector",
  "por_emision",
  "none",
];
const FILTRO_KINDS = [
  "prefix",
  "prefix_with_sub",
  "contains_fuel",
  "in_fuel_list",
  "by_emission_list",
  "all",
  "custom_callable",
];

type ModuleLite = { id: number; code: string; label: string; submodules: { id: number; code: string; label: string }[] };

export function ChartsTab() {
  const [charts, setCharts] = useState<ChartConfigItem[]>([]);
  const [modules, setModules] = useState<ModuleLite[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<ChartConfigItem | null>(null);
  const [filterModule, setFilterModule] = useState<number | "">("");

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [chartsResp, modulesResp] = await Promise.all([
        catalogMetaChartApi.list(filterModule === "" ? undefined : (filterModule as number)),
        catalogMetaModuleApi.tree(),
      ]);
      setCharts(chartsResp.items);
      setModules(
        modulesResp.items.map((m: ChartModuleItem) => ({
          id: m.id,
          code: m.code,
          label: m.label,
          submodules: m.submodules.map((s) => ({ id: s.id, code: s.code, label: s.label })),
        })),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }, [filterModule]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const moduleById = useMemo(() => new Map(modules.map((m) => [m.id, m])), [modules]);

  const grouped = useMemo(() => {
    const m: Record<string, ChartConfigItem[]> = {};
    for (const c of charts) {
      const modLabel = moduleById.get(c.module_id)?.label ?? `Módulo ${c.module_id}`;
      (m[modLabel] ||= []).push(c);
    }
    return m;
  }, [charts, moduleById]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <label style={{ fontSize: 13 }}>
          Módulo:{" "}
          <select
            value={filterModule}
            onChange={(e) => setFilterModule(e.target.value === "" ? "" : Number(e.target.value))}
            style={fieldStyle}
          >
            <option value="">(todos)</option>
            {modules.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </label>
        <Button variant="ghost" onClick={reload} disabled={loading}>
          {loading ? "Cargando…" : "Recargar"}
        </Button>
        <div style={{ flex: 1 }} />
        <small style={{ opacity: 0.7 }}>{charts.length} gráficas</small>
      </div>

      {error ? <ErrorBox>{error}</ErrorBox> : null}

      {Object.entries(grouped).map(([modLabel, items]) => (
        <div key={modLabel} style={groupCardStyle}>
          <div style={groupHeaderStyle}>
            {modLabel} <small style={{ opacity: 0.55 }}>({items.length})</small>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead style={{ background: "rgba(255,255,255,0.03)" }}>
              <tr>
                <Th style={{ width: 180 }}>Tipo</Th>
                <Th>Título</Th>
                <Th style={{ width: 180 }}>Variable</Th>
                <Th style={{ width: 130 }}>Agrupación</Th>
                <Th style={{ width: 80 }}>Visible</Th>
                <Th style={{ width: 110 }}>Detalles</Th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <ChartRow
                  key={c.id}
                  chart={c}
                  onOpenDetail={() => setEditing(c)}
                  onUpdate={async (patch) => {
                    try {
                      await catalogMetaChartApi.update(c.id, patch);
                      await reload();
                    } catch (e) {
                      setError(e instanceof Error ? e.message : "Error");
                    }
                  }}
                />
              ))}
            </tbody>
          </table>
        </div>
      ))}

      {editing ? (
        <ChartDetailModal
          chart={editing}
          modules={modules}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            await reload();
          }}
        />
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------

function ChartRow({
  chart,
  onOpenDetail,
  onUpdate,
}: {
  chart: ChartConfigItem;
  onOpenDetail: () => void;
  onUpdate: (patch: Parameters<typeof catalogMetaChartApi.update>[1]) => Promise<void>;
}) {
  const [draftLabel, setDraftLabel] = useState(chart.label_titulo);
  const [draftAgr, setDraftAgr] = useState(chart.agrupar_por_default);
  useEffect(() => setDraftLabel(chart.label_titulo), [chart.label_titulo]);
  useEffect(() => setDraftAgr(chart.agrupar_por_default), [chart.agrupar_por_default]);

  const labelDirty = draftLabel !== chart.label_titulo;
  const agrDirty = draftAgr !== chart.agrupar_por_default;
  return (
    <tr style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}>
      <Td><code style={{ fontSize: 11 }}>{chart.tipo}</code></Td>
      <Td>
        <input
          type="text"
          value={draftLabel}
          onChange={(e) => setDraftLabel(e.target.value)}
          onBlur={() => {
            if (labelDirty) void onUpdate({ label_titulo: draftLabel });
          }}
          style={{ ...fieldStyle, width: "100%" }}
        />
      </Td>
      <Td>
        <code style={{ fontSize: 11 }}>{chart.variable_default}</code>
      </Td>
      <Td>
        <select
          value={draftAgr}
          onChange={(e) => {
            setDraftAgr(e.target.value);
            void onUpdate({ agrupar_por_default: e.target.value });
          }}
          style={fieldStyle}
        >
          {AGRUPACIONES.map((a) => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>
        {agrDirty ? <span style={{ fontSize: 9, opacity: 0.6 }}> •</span> : null}
      </Td>
      <Td>
        <input
          type="checkbox"
          checked={chart.is_visible}
          onChange={(e) => void onUpdate({ is_visible: e.target.checked })}
        />
      </Td>
      <Td>
        <Button variant="ghost" onClick={onOpenDetail}>
          Editar
        </Button>
      </Td>
    </tr>
  );
}

// ---------------------------------------------------------------------------

function ChartDetailModal({
  chart,
  modules,
  onClose,
  onSaved,
}: {
  chart: ChartConfigItem;
  modules: ModuleLite[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [draft, setDraft] = useState<ChartConfigItem>(chart);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await catalogMetaChartApi.update(chart.id, {
        module_id: draft.module_id,
        submodule_id: draft.submodule_id,
        label_titulo: draft.label_titulo,
        label_figura: draft.label_figura,
        variable_default: draft.variable_default,
        filtro_kind: draft.filtro_kind,
        filtro_params_json: draft.filtro_params_json,
        agrupar_por_default: draft.agrupar_por_default,
        agrupaciones_permitidas_json: draft.agrupaciones_permitidas_json,
        color_fn_key: draft.color_fn_key,
        flags_json: draft.flags_json,
        msg_sin_datos: draft.msg_sin_datos,
        data_explorer_filters_json: draft.data_explorer_filters_json,
        is_visible: draft.is_visible,
        sort_order: draft.sort_order,
      });
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
      setSaving(false);
    }
  };

  const currentModule = modules.find((m) => m.id === draft.module_id);
  const flags: Record<string, unknown> = (draft.flags_json as Record<string, unknown> | null) ?? {};

  const toggleFlag = (key: string) => {
    setDraft({ ...draft, flags_json: { ...flags, [key]: !flags[key] } });
  };

  const toggleAgr = (a: string) => {
    const current = draft.agrupaciones_permitidas_json ?? [];
    const next = current.includes(a) ? current.filter((x) => x !== a) : [...current, a];
    setDraft({ ...draft, agrupaciones_permitidas_json: next });
  };

  return (
    <Modal open onClose={onClose} title={`Editar gráfica · ${chart.tipo}`} wide>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {error ? <ErrorBox>{error}</ErrorBox> : null}

        <Section title="Identidad">
          <FieldRow>
            <Field label="Tipo (readonly)">
              <code style={{ fontSize: 12 }}>{draft.tipo}</code>
            </Field>
            <Field label="Figura">
              <input
                type="text"
                value={draft.label_figura ?? ""}
                onChange={(e) => setDraft({ ...draft, label_figura: e.target.value || null })}
                style={fieldStyle}
              />
            </Field>
          </FieldRow>
          <Field label="Título">
            <input
              type="text"
              value={draft.label_titulo}
              onChange={(e) => setDraft({ ...draft, label_titulo: e.target.value })}
              style={{ ...fieldStyle, width: "100%" }}
            />
          </Field>
          <Field label="Mensaje sin datos">
            <input
              type="text"
              value={draft.msg_sin_datos ?? ""}
              onChange={(e) => setDraft({ ...draft, msg_sin_datos: e.target.value || null })}
              style={{ ...fieldStyle, width: "100%" }}
            />
          </Field>
        </Section>

        <Section title="Jerarquía">
          <FieldRow>
            <Field label="Módulo">
              <select
                value={draft.module_id}
                onChange={(e) => setDraft({ ...draft, module_id: Number(e.target.value), submodule_id: null })}
                style={fieldStyle}
              >
                {modules.map((m) => (
                  <option key={m.id} value={m.id}>{m.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Submódulo">
              <select
                value={draft.submodule_id ?? ""}
                onChange={(e) => setDraft({ ...draft, submodule_id: e.target.value ? Number(e.target.value) : null })}
                style={fieldStyle}
                disabled={!currentModule?.submodules.length}
              >
                <option value="">(ninguno)</option>
                {currentModule?.submodules.map((s) => (
                  <option key={s.id} value={s.id}>{s.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Orden">
              <input
                type="number"
                value={draft.sort_order}
                onChange={(e) => setDraft({ ...draft, sort_order: Number(e.target.value) })}
                style={{ ...fieldStyle, width: 80 }}
              />
            </Field>
          </FieldRow>
        </Section>

        <Section title="Datos & filtro">
          <FieldRow>
            <Field label="Variable default">
              <input
                type="text"
                value={draft.variable_default}
                onChange={(e) => setDraft({ ...draft, variable_default: e.target.value })}
                style={fieldStyle}
              />
            </Field>
            <Field label="Filtro kind">
              <select
                value={draft.filtro_kind}
                onChange={(e) => setDraft({ ...draft, filtro_kind: e.target.value })}
                style={fieldStyle}
              >
                {FILTRO_KINDS.map((k) => (
                  <option key={k} value={k}>{k}</option>
                ))}
              </select>
            </Field>
          </FieldRow>
          <Field label="Filtro params (JSON)">
            <JsonTextarea
              value={draft.filtro_params_json}
              onChange={(v) => setDraft({ ...draft, filtro_params_json: v })}
            />
          </Field>
          <Field label="Data Explorer filters (JSON)">
            <JsonTextarea
              value={draft.data_explorer_filters_json}
              onChange={(v) => setDraft({ ...draft, data_explorer_filters_json: v })}
            />
          </Field>
        </Section>

        <Section title="Agrupación">
          <FieldRow>
            <Field label="Default">
              <select
                value={draft.agrupar_por_default}
                onChange={(e) => setDraft({ ...draft, agrupar_por_default: e.target.value })}
                style={fieldStyle}
              >
                {AGRUPACIONES.map((a) => (
                  <option key={a} value={a}>{a}</option>
                ))}
              </select>
            </Field>
            <Field label="Color fn">
              <select
                value={draft.color_fn_key}
                onChange={(e) => setDraft({ ...draft, color_fn_key: e.target.value })}
                style={fieldStyle}
              >
                {COLOR_FNS.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </Field>
          </FieldRow>
          <Field label="Permitidas">
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {AGRUPACIONES.map((a) => (
                <label key={a} style={chipLabelStyle}>
                  <input
                    type="checkbox"
                    checked={(draft.agrupaciones_permitidas_json ?? []).includes(a)}
                    onChange={() => toggleAgr(a)}
                  />
                  {a}
                </label>
              ))}
            </div>
          </Field>
        </Section>

        <Section title="Flags">
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {[
              "es_capacidad",
              "es_porcentaje",
              "es_emision",
              "soporta_pareto",
              "has_loc",
              "has_sub_filtro",
            ].map((f) => (
              <label key={f} style={chipLabelStyle}>
                <input type="checkbox" checked={Boolean(flags[f])} onChange={() => toggleFlag(f)} />
                {f}
              </label>
            ))}
            <label style={chipLabelStyle}>
              <input
                type="checkbox"
                checked={draft.is_visible}
                onChange={(e) => setDraft({ ...draft, is_visible: e.target.checked })}
              />
              is_visible
            </label>
          </div>
          <Field label="sub_filtro_label">
            <input
              type="text"
              value={String(flags.sub_filtro_label ?? "")}
              onChange={(e) =>
                setDraft({ ...draft, flags_json: { ...flags, sub_filtro_label: e.target.value || null } })
              }
              style={{ ...fieldStyle, width: 200 }}
              placeholder="p.ej. Uso / Modo / Combustible"
            />
          </Field>
        </Section>

        <SubfiltersSection
          chartId={chart.id}
          initial={draft.subfilters}
          onChangeBackendReload={() => {}}
        />

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", paddingTop: 6 }}>
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancelar
          </Button>
          <Button onClick={save} disabled={saving}>
            {saving ? "Guardando…" : "Guardar"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
//  Sub-filtros (3.3.H — inline en el modal del chart)
// ---------------------------------------------------------------------------

function SubfiltersSection({
  chartId,
  initial,
  onChangeBackendReload,
}: {
  chartId: number;
  initial: ChartSubfilterItem[];
  onChangeBackendReload: () => void;
}) {
  const [items, setItems] = useState<ChartSubfilterItem[]>(initial);
  const [creating, setCreating] = useState<
    { code: string; display_label: string; group_label: string } | null
  >(null);
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    if (!creating) return;
    try {
      const row = await catalogMetaChartApi.createSubfilter({
        chart_id: chartId,
        code: creating.code.trim(),
        display_label: creating.display_label || null,
        group_label: creating.group_label || null,
        sort_order: items.length,
      });
      setItems([...items, row]);
      setCreating(null);
      onChangeBackendReload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    }
  };

  const remove = async (sub: ChartSubfilterItem) => {
    if (!confirm(`¿Eliminar sub-filtro ${sub.code}?`)) return;
    try {
      await catalogMetaChartApi.deleteSubfilter(sub.id);
      setItems(items.filter((x) => x.id !== sub.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    }
  };

  const update = async (sub: ChartSubfilterItem, patch: Partial<ChartSubfilterItem>) => {
    try {
      const updated = await catalogMetaChartApi.updateSubfilter(sub.id, patch);
      setItems(items.map((x) => (x.id === sub.id ? updated : x)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    }
  };

  return (
    <Section title={`Sub-filtros (${items.length})`}>
      {error ? <ErrorBox>{error}</ErrorBox> : null}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 6 }}>
        {items.map((s) => (
          <span
            key={s.id}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: "2px 8px",
              borderRadius: 999,
              fontSize: 12,
              background: "rgba(80,140,255,0.12)",
              border: "1px solid rgba(80,140,255,0.35)",
            }}
          >
            <code>{s.code}</code>
            <input
              type="text"
              value={s.display_label ?? ""}
              placeholder="label"
              onChange={(e) => update(s, { display_label: e.target.value || null })}
              style={{ ...fieldStyle, width: 100, fontSize: 11 }}
            />
            <button
              type="button"
              onClick={() => remove(s)}
              style={{ background: "transparent", border: "none", color: "inherit", cursor: "pointer", opacity: 0.65 }}
            >
              ✕
            </button>
          </span>
        ))}
        {items.length === 0 ? <small style={{ opacity: 0.55 }}>Sin sub-filtros.</small> : null}
      </div>
      {creating ? (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          <input
            type="text"
            placeholder="Código"
            value={creating.code}
            onChange={(e) => setCreating({ ...creating, code: e.target.value })}
            style={{ ...fieldStyle, width: 120 }}
          />
          <input
            type="text"
            placeholder="Label"
            value={creating.display_label}
            onChange={(e) => setCreating({ ...creating, display_label: e.target.value })}
            style={{ ...fieldStyle, width: 160 }}
          />
          <input
            type="text"
            placeholder="Grupo (Modo/Uso)"
            value={creating.group_label}
            onChange={(e) => setCreating({ ...creating, group_label: e.target.value })}
            style={{ ...fieldStyle, width: 120 }}
          />
          <Button onClick={create} disabled={!creating.code.trim()}>
            Agregar
          </Button>
          <Button variant="ghost" onClick={() => setCreating(null)}>
            ✕
          </Button>
        </div>
      ) : (
        <Button
          variant="ghost"
          onClick={() => setCreating({ code: "", display_label: "", group_label: "" })}
        >
          + Sub-filtro
        </Button>
      )}
    </Section>
  );
}

// ---------------------------------------------------------------------------

function JsonTextarea({
  value,
  onChange,
}: {
  value: unknown;
  onChange: (next: Record<string, unknown> | null) => void;
}) {
  const [text, setText] = useState(() => JSON.stringify(value ?? null, null, 2));
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => setText(JSON.stringify(value ?? null, null, 2)), [value]);
  return (
    <>
      <textarea
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          try {
            const parsed = e.target.value.trim() === "" ? null : JSON.parse(e.target.value);
            setErr(null);
            onChange(parsed as Record<string, unknown> | null);
          } catch (exc) {
            setErr(exc instanceof Error ? exc.message : "JSON inválido");
          }
        }}
        style={{
          ...fieldStyle,
          width: "100%",
          minHeight: 80,
          fontFamily: "var(--font-mono, monospace)",
          fontSize: 11,
        }}
      />
      {err ? <small style={{ color: "rgba(255,180,180,0.9)" }}>{err}</small> : null}
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={sectionStyle}>
      <div style={{ fontSize: 12, fontWeight: 600, opacity: 0.7, marginBottom: 6 }}>{title}</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>{children}</div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <span style={{ fontSize: 11, opacity: 0.7 }}>{label}</span>
      {children}
    </label>
  );
}

function FieldRow({ children }: { children: React.ReactNode }) {
  return <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>{children}</div>;
}

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

function Th({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <th
      style={{
        textAlign: "left",
        fontSize: 12,
        padding: "6px 10px",
        color: "var(--muted)",
        fontWeight: 500,
        ...style,
      }}
    >
      {children}
    </th>
  );
}

function Td({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return <td style={{ padding: "5px 10px", fontSize: 13, ...style }}>{children}</td>;
}

const fieldStyle: React.CSSProperties = {
  background: "transparent",
  color: "inherit",
  border: "1px solid rgba(255,255,255,0.12)",
  borderRadius: 4,
  padding: "3px 8px",
  fontSize: 13,
};

const groupCardStyle: React.CSSProperties = {
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 10,
  overflow: "hidden",
};

const groupHeaderStyle: React.CSSProperties = {
  padding: "8px 12px",
  borderBottom: "1px solid rgba(255,255,255,0.08)",
  background: "rgba(255,255,255,0.03)",
  fontSize: 13,
  fontWeight: 600,
};

const sectionStyle: React.CSSProperties = {
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 8,
  padding: 10,
  background: "rgba(255,255,255,0.02)",
};

const chipLabelStyle: React.CSSProperties = {
  display: "inline-flex",
  gap: 4,
  alignItems: "center",
  fontSize: 12,
  padding: "3px 8px",
  border: "1px solid rgba(255,255,255,0.12)",
  borderRadius: 999,
  cursor: "pointer",
};
