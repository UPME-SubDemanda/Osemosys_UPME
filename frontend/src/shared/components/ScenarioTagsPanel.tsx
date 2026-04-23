/**
 * Panel de gestión de etiquetas para un escenario específico.
 *
 * - Agrupa los tags asignados por categoría (ordenadas por hierarchy_level).
 * - Cada chip tiene "×" que abre `ConfirmDialog` antes de quitarlo.
 * - Por categoría muestra un `<select>` con los tags disponibles para asignar.
 * - Maneja el diálogo de conflicto de exclusividad combinatoria (force=true).
 */
import { useMemo, useState } from "react";

import {
  TagAssignmentConflictError,
  scenariosApi,
} from "@/features/scenarios/api/scenariosApi";
import { ConfirmDialog } from "@/shared/components/ConfirmDialog";
import { ScenarioTagChip } from "@/shared/components/ScenarioTagChip";
import type {
  ScenarioTag,
  ScenarioTagCategory,
  ScenarioTagConflict,
} from "@/types/domain";

type Props = {
  scenarioId: number;
  scenarioName: string;
  tags: ScenarioTag[];
  categories: ScenarioTagCategory[];
  availableTags: ScenarioTag[];
  canEdit: boolean;
  onTagsChange: (next: ScenarioTag[]) => void;
};

export function ScenarioTagsPanel({
  scenarioId,
  scenarioName,
  tags,
  categories,
  availableTags,
  canEdit,
  onTagsChange,
}: Props) {
  const [toRemove, setToRemove] = useState<ScenarioTag | null>(null);
  const [conflict, setConflict] = useState<{
    tagId: number;
    conflict: ScenarioTagConflict;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const tagsByCategory = useMemo(() => {
    const map = new Map<number, ScenarioTag[]>();
    for (const t of tags) {
      const arr = map.get(t.category_id) ?? [];
      arr.push(t);
      map.set(t.category_id, arr);
    }
    return map;
  }, [tags]);

  const tagsById = useMemo(() => {
    const m = new Map<number, ScenarioTag>();
    for (const t of availableTags) m.set(t.id, t);
    for (const t of tags) m.set(t.id, t);
    return m;
  }, [availableTags, tags]);

  async function assignTag(tagId: number, force = false) {
    setError(null);
    setBusy(true);
    try {
      const updated = await scenariosApi.assignTagToScenario(
        scenarioId,
        tagId,
        force,
      );
      onTagsChange(updated);
      setConflict(null);
    } catch (err) {
      if (err instanceof TagAssignmentConflictError) {
        setConflict({ tagId, conflict: err.conflict });
      } else {
        setError(
          (err as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail ??
            (err as Error)?.message ??
            "No se pudo asignar la etiqueta.",
        );
      }
    } finally {
      setBusy(false);
    }
  }

  async function removeTag(tag: ScenarioTag) {
    setError(null);
    setBusy(true);
    try {
      const updated = await scenariosApi.removeTagFromScenario(
        scenarioId,
        tag.id,
      );
      onTagsChange(updated);
    } catch (err) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "No se pudo quitar la etiqueta.",
      );
    } finally {
      setBusy(false);
      setToRemove(null);
    }
  }

  const conflictTag = conflict ? tagsById.get(conflict.tagId) : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {error ? (
        <div
          style={{
            color: "#fca5a5",
            fontSize: 13,
            background: "rgba(239,68,68,0.1)",
            border: "1px solid rgba(239,68,68,0.3)",
            padding: "6px 10px",
            borderRadius: 6,
          }}
        >
          {error}
        </div>
      ) : null}

      {categories.map((cat) => {
        const assigned = tagsByCategory.get(cat.id) ?? [];
        const candidates = availableTags.filter(
          (t) =>
            t.category_id === cat.id &&
            !assigned.some((a) => a.id === t.id),
        );
        const canAddMore =
          cat.max_tags_per_scenario == null ||
          assigned.length < cat.max_tags_per_scenario ||
          cat.max_tags_per_scenario === 1; // max=1 siempre permite reemplazar
        return (
          <div
            key={cat.id}
            style={{
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: 8,
              padding: "8px 10px",
              background: "rgba(255,255,255,0.02)",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 6,
                gap: 8,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: cat.default_color,
                    display: "inline-block",
                  }}
                />
                <strong style={{ fontSize: 13 }}>{cat.name}</strong>
                <span style={{ fontSize: 11, opacity: 0.6 }}>
                  (jerarquía {cat.hierarchy_level}
                  {cat.max_tags_per_scenario === 1 ? ", única" : ""}
                  {cat.is_exclusive_combination ? ", combinación exclusiva" : ""}
                  )
                </span>
              </div>
            </div>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 6,
                alignItems: "center",
              }}
            >
              {assigned.length === 0 ? (
                <span style={{ fontSize: 12, opacity: 0.55 }}>
                  Sin etiquetas de esta categoría.
                </span>
              ) : (
                assigned.map((t) => (
                  <ScenarioTagChip
                    key={t.id}
                    tag={t}
                    onRemove={canEdit ? () => setToRemove(t) : undefined}
                    size="sm"
                  />
                ))
              )}
              {canEdit && canAddMore && candidates.length > 0 ? (
                <select
                  defaultValue=""
                  disabled={busy}
                  onChange={(e) => {
                    const v = e.target.value;
                    e.currentTarget.value = "";
                    if (v) assignTag(Number(v));
                  }}
                  style={{
                    background: "rgba(255,255,255,0.06)",
                    border: "1px solid rgba(255,255,255,0.12)",
                    color: "#fff",
                    borderRadius: 6,
                    fontSize: 12,
                    padding: "3px 6px",
                  }}
                >
                  <option value="">+ Agregar…</option>
                  {candidates.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
                </select>
              ) : null}
            </div>
          </div>
        );
      })}

      <ConfirmDialog
        open={toRemove !== null}
        title="Quitar etiqueta"
        message={
          toRemove ? (
            <>
              ¿Quitar la etiqueta <strong>{toRemove.name}</strong> del escenario{" "}
              <strong>{scenarioName}</strong>?
            </>
          ) : (
            ""
          )
        }
        danger
        confirmLabel="Quitar"
        onConfirm={() => toRemove && removeTag(toRemove)}
        onCancel={() => setToRemove(null)}
      />

      <ConfirmDialog
        open={conflict !== null}
        title="Conflicto de etiquetas"
        message={
          conflict ? (
            <>
              El escenario <strong>{conflict.conflict.scenario_name}</strong> ya
              tiene la etiqueta{" "}
              <strong>{conflict.conflict.conflicting_tag_name}</strong> con la
              misma combinación. Si continúas, se le quitará esa etiqueta para
              asignársela a <strong>{scenarioName}</strong>
              {conflictTag ? (
                <>
                  {" "}
                  (etiqueta: <strong>{conflictTag.name}</strong>)
                </>
              ) : null}
              .
            </>
          ) : (
            ""
          )
        }
        confirmLabel="Sí, asignar y quitar del otro"
        danger
        onConfirm={() => conflict && assignTag(conflict.tagId, true)}
        onCancel={() => setConflict(null)}
      />
    </div>
  );
}
