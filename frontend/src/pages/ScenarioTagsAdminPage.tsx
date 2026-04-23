/**
 * Administración de categorías y etiquetas de escenario.
 *
 * Solo visible para usuarios con `can_manage_catalogs`.
 * - CRUD de categorías con jerarquía (hierarchy_level), cap máximo por escenario
 *   y flag de exclusividad combinatoria.
 * - CRUD de etiquetas (nombre, color, orden, categoría).
 */
import { useEffect, useMemo, useState } from "react";

import { scenariosApi } from "@/features/scenarios/api/scenariosApi";
import { useCurrentUser } from "@/app/providers/useCurrentUser";
import { useToast } from "@/app/providers/useToast";
import { Button } from "@/shared/components/Button";
import { Card } from "@/shared/components/Card";
import { ConfirmDialog } from "@/shared/components/ConfirmDialog";
import { Modal } from "@/shared/components/Modal";
import { TextField } from "@/shared/components/TextField";
import type { ScenarioTag, ScenarioTagCategory } from "@/types/domain";

const COLOR_PALETTE = [
  "#3B82F6",
  "#2563EB",
  "#0EA5E9",
  "#14B8A6",
  "#22C55E",
  "#EAB308",
  "#F59E0B",
  "#EA580C",
  "#DC2626",
  "#EC4899",
  "#A855F7",
  "#7C3AED",
  "#64748B",
  "#16A34A",
] as const;

type CategoryForm = {
  id: number | null;
  name: string;
  hierarchy_level: number;
  sort_order: number;
  max_tags_per_scenario: number | null;
  is_exclusive_combination: boolean;
  default_color: string;
};

const EMPTY_CATEGORY: CategoryForm = {
  id: null,
  name: "",
  hierarchy_level: 1,
  sort_order: 0,
  max_tags_per_scenario: 1,
  is_exclusive_combination: false,
  default_color: "#64748B",
};

type TagForm = {
  id: number | null;
  category_id: number;
  name: string;
  color: string;
  sort_order: number;
  is_exclusive_combination: boolean;
};

export function ScenarioTagsAdminPage() {
  const { user } = useCurrentUser();
  const toast = useToast();
  const [categories, setCategories] = useState<ScenarioTagCategory[]>([]);
  const [tags, setTags] = useState<ScenarioTag[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryForm, setCategoryForm] = useState<CategoryForm | null>(null);
  const [tagForm, setTagForm] = useState<TagForm | null>(null);
  const [categoryToDelete, setCategoryToDelete] = useState<ScenarioTagCategory | null>(null);
  const [tagToDelete, setTagToDelete] = useState<ScenarioTag | null>(null);

  const canManage = Boolean(user?.can_manage_catalogs);

  async function reload() {
    setLoading(true);
    try {
      const [cats, ts] = await Promise.all([
        scenariosApi.listScenarioTagCategories(),
        scenariosApi.listScenarioTags(),
      ]);
      setCategories(cats);
      setTags(ts);
    } catch (err) {
      toast.push(
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "No se pudo cargar el catálogo.",
        "error",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
  }, []);

  const tagsByCategory = useMemo(() => {
    const m = new Map<number, ScenarioTag[]>();
    for (const t of tags) {
      const arr = m.get(t.category_id) ?? [];
      arr.push(t);
      m.set(t.category_id, arr);
    }
    return m;
  }, [tags]);

  async function saveCategory() {
    if (!categoryForm) return;
    try {
      if (categoryForm.id == null) {
        await scenariosApi.createScenarioTagCategory({
          name: categoryForm.name,
          hierarchy_level: categoryForm.hierarchy_level,
          sort_order: categoryForm.sort_order,
          max_tags_per_scenario: categoryForm.max_tags_per_scenario,
          is_exclusive_combination: categoryForm.is_exclusive_combination,
          default_color: categoryForm.default_color,
        });
      } else {
        await scenariosApi.updateScenarioTagCategory(categoryForm.id, {
          name: categoryForm.name,
          hierarchy_level: categoryForm.hierarchy_level,
          sort_order: categoryForm.sort_order,
          max_tags_per_scenario: categoryForm.max_tags_per_scenario,
          is_exclusive_combination: categoryForm.is_exclusive_combination,
          default_color: categoryForm.default_color,
        });
      }
      setCategoryForm(null);
      await reload();
      toast.push("Categoría guardada.", "success");
    } catch (err) {
      toast.push(
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "No se pudo guardar la categoría.",
        "error",
      );
    }
  }

  async function saveTag() {
    if (!tagForm) return;
    try {
      if (tagForm.id == null) {
        await scenariosApi.createScenarioTag({
          category_id: tagForm.category_id,
          name: tagForm.name,
          color: tagForm.color,
          sort_order: tagForm.sort_order,
          is_exclusive_combination: tagForm.is_exclusive_combination,
        });
      } else {
        await scenariosApi.updateScenarioTag(tagForm.id, {
          category_id: tagForm.category_id,
          name: tagForm.name,
          color: tagForm.color,
          sort_order: tagForm.sort_order,
          is_exclusive_combination: tagForm.is_exclusive_combination,
        });
      }
      setTagForm(null);
      await reload();
      toast.push("Etiqueta guardada.", "success");
    } catch (err) {
      toast.push(
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "No se pudo guardar la etiqueta.",
        "error",
      );
    }
  }

  async function confirmDeleteCategory() {
    if (!categoryToDelete) return;
    try {
      await scenariosApi.deleteScenarioTagCategory(categoryToDelete.id);
      await reload();
      toast.push("Categoría eliminada.", "success");
    } catch (err) {
      toast.push(
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "No se pudo eliminar la categoría.",
        "error",
      );
    } finally {
      setCategoryToDelete(null);
    }
  }

  async function confirmDeleteTag() {
    if (!tagToDelete) return;
    try {
      await scenariosApi.deleteScenarioTag(tagToDelete.id);
      await reload();
      toast.push("Etiqueta eliminada.", "success");
    } catch (err) {
      toast.push(
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "No se pudo eliminar la etiqueta.",
        "error",
      );
    } finally {
      setTagToDelete(null);
    }
  }

  if (!canManage) {
    return (
      <div style={{ padding: 24 }}>
        No tienes permisos para administrar categorías y etiquetas.
      </div>
    );
  }

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <h2 style={{ margin: 0 }}>Etiquetas y categorías</h2>
          <p style={{ margin: "4px 0 0", opacity: 0.7, fontSize: 13 }}>
            Las categorías con jerarquía 1 aparecen primero. Marca
            «combinación exclusiva» para que dos escenarios no puedan compartir
            la misma combinación de etiquetas (ej. «Oficial» + «PA»).
          </p>
        </div>
        <Button onClick={() => setCategoryForm(EMPTY_CATEGORY)}>
          + Nueva categoría
        </Button>
      </div>

      {loading ? (
        <div>Cargando…</div>
      ) : (
        categories.map((cat) => {
          const catTags = tagsByCategory.get(cat.id) ?? [];
          return (
            <Card key={cat.id}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 10,
                  gap: 12,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span
                    style={{
                      width: 12,
                      height: 12,
                      borderRadius: "50%",
                      background: cat.default_color,
                    }}
                  />
                  <div>
                    <strong>{cat.name}</strong>
                    <div style={{ fontSize: 12, opacity: 0.65 }}>
                      Jerarquía {cat.hierarchy_level} · Orden {cat.sort_order} ·{" "}
                      {cat.max_tags_per_scenario == null
                        ? "ilimitadas"
                        : `máx. ${cat.max_tags_per_scenario} por escenario`}
                      {cat.is_exclusive_combination
                        ? " · combinación exclusiva"
                        : ""}
                    </div>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  <button
                    className="btn btn--ghost"
                    type="button"
                    onClick={() =>
                      setTagForm({
                        id: null,
                        category_id: cat.id,
                        name: "",
                        color: cat.default_color,
                        sort_order: (catTags.length + 1) * 10,
                        is_exclusive_combination: cat.is_exclusive_combination,
                      })
                    }
                  >
                    + Etiqueta
                  </button>
                  <button
                    className="btn btn--ghost"
                    type="button"
                    onClick={() =>
                      setCategoryForm({
                        id: cat.id,
                        name: cat.name,
                        hierarchy_level: cat.hierarchy_level,
                        sort_order: cat.sort_order,
                        max_tags_per_scenario: cat.max_tags_per_scenario,
                        is_exclusive_combination: cat.is_exclusive_combination,
                        default_color: cat.default_color,
                      })
                    }
                  >
                    Editar
                  </button>
                  <button
                    className="btn btn--danger"
                    type="button"
                    onClick={() => setCategoryToDelete(cat)}
                  >
                    Eliminar
                  </button>
                </div>
              </div>
              {catTags.length === 0 ? (
                <div style={{ fontSize: 13, opacity: 0.6 }}>
                  Sin etiquetas. Crea la primera con «+ Etiqueta».
                </div>
              ) : (
                <table style={{ width: "100%", fontSize: 13 }}>
                  <thead>
                    <tr style={{ textAlign: "left", opacity: 0.6 }}>
                      <th>Etiqueta</th>
                      <th>Color</th>
                      <th>Orden</th>
                      <th title="Si está marcada, la combinación de esta etiqueta con las de otras categorías debe ser única entre escenarios.">
                        Única
                      </th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {catTags.map((t) => (
                      <tr key={t.id}>
                        <td>
                          <span
                            style={{
                              display: "inline-block",
                              padding: "2px 8px",
                              borderRadius: 6,
                              background: t.color,
                              color: "#fff",
                              fontWeight: 600,
                            }}
                          >
                            {t.name}
                          </span>
                        </td>
                        <td style={{ fontFamily: "monospace" }}>{t.color}</td>
                        <td>{t.sort_order}</td>
                        <td>{t.is_exclusive_combination ? "Sí" : "No"}</td>
                        <td style={{ textAlign: "right" }}>
                          <button
                            className="btn btn--ghost"
                            type="button"
                            onClick={() =>
                              setTagForm({
                                id: t.id,
                                category_id: t.category_id,
                                name: t.name,
                                color: t.color,
                                sort_order: t.sort_order,
                                is_exclusive_combination: Boolean(
                                  t.is_exclusive_combination,
                                ),
                              })
                            }
                          >
                            Editar
                          </button>
                          <button
                            className="btn btn--danger"
                            type="button"
                            onClick={() => setTagToDelete(t)}
                          >
                            Eliminar
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
          );
        })
      )}

      {/* Modal categoría */}
      <Modal
        open={categoryForm !== null}
        title={categoryForm?.id == null ? "Nueva categoría" : "Editar categoría"}
        onClose={() => setCategoryForm(null)}
        footer={
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => setCategoryForm(null)}
            >
              Cancelar
            </button>
            <button
              type="button"
              className="btn btn--primary"
              onClick={saveCategory}
              disabled={!categoryForm?.name.trim()}
            >
              Guardar
            </button>
          </div>
        }
      >
        {categoryForm ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <TextField
              label="Nombre"
              value={categoryForm.name}
              onChange={(e) =>
                setCategoryForm({ ...categoryForm, name: e.target.value })
              }
            />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <TextField
                label="Jerarquía (1 = superior)"
                type="number"
                value={String(categoryForm.hierarchy_level)}
                onChange={(e) =>
                  setCategoryForm({
                    ...categoryForm,
                    hierarchy_level: Math.max(1, Number(e.target.value) || 1),
                  })
                }
              />
              <TextField
                label="Orden dentro del nivel"
                type="number"
                value={String(categoryForm.sort_order)}
                onChange={(e) =>
                  setCategoryForm({
                    ...categoryForm,
                    sort_order: Number(e.target.value) || 0,
                  })
                }
              />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <label style={{ fontSize: 13 }}>
                Máximo de etiquetas por escenario
              </label>
              <select
                value={
                  categoryForm.max_tags_per_scenario == null
                    ? "null"
                    : String(categoryForm.max_tags_per_scenario)
                }
                onChange={(e) => {
                  const v = e.target.value;
                  setCategoryForm({
                    ...categoryForm,
                    max_tags_per_scenario:
                      v === "null" ? null : Number(v),
                  });
                }}
                style={{ padding: 6 }}
              >
                <option value="1">1 — exclusiva por escenario</option>
                <option value="2">2</option>
                <option value="3">3</option>
                <option value="null">Sin límite</option>
              </select>
            </div>
            <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 13 }}>
              <input
                type="checkbox"
                checked={categoryForm.is_exclusive_combination}
                onChange={(e) =>
                  setCategoryForm({
                    ...categoryForm,
                    is_exclusive_combination: e.target.checked,
                  })
                }
              />
              Combinación exclusiva entre escenarios (ej. solo un escenario
              puede ser «Oficial» para una misma etiqueta de menor jerarquía).
            </label>
            <ColorSwatch
              value={categoryForm.default_color}
              onChange={(v) =>
                setCategoryForm({ ...categoryForm, default_color: v })
              }
            />
          </div>
        ) : null}
      </Modal>

      {/* Modal tag */}
      <Modal
        open={tagForm !== null}
        title={tagForm?.id == null ? "Nueva etiqueta" : "Editar etiqueta"}
        onClose={() => setTagForm(null)}
        footer={
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => setTagForm(null)}
            >
              Cancelar
            </button>
            <button
              type="button"
              className="btn btn--primary"
              onClick={saveTag}
              disabled={!tagForm?.name.trim()}
            >
              Guardar
            </button>
          </div>
        }
      >
        {tagForm ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <label style={{ fontSize: 13 }}>Categoría</label>
              <select
                value={String(tagForm.category_id)}
                onChange={(e) =>
                  setTagForm({ ...tagForm, category_id: Number(e.target.value) })
                }
                style={{ padding: 6 }}
              >
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} (jerarquía {c.hierarchy_level})
                  </option>
                ))}
              </select>
            </div>
            <TextField
              label="Nombre"
              value={tagForm.name}
              onChange={(e) => setTagForm({ ...tagForm, name: e.target.value })}
            />
            <TextField
              label="Orden"
              type="number"
              value={String(tagForm.sort_order)}
              onChange={(e) =>
                setTagForm({
                  ...tagForm,
                  sort_order: Number(e.target.value) || 0,
                })
              }
            />
            <ColorSwatch
              value={tagForm.color}
              onChange={(v) => setTagForm({ ...tagForm, color: v })}
            />
            <div
              style={{
                border: "1px solid rgba(255,255,255,0.08)",
                borderRadius: 8,
                padding: 10,
                background: "rgba(255,255,255,0.02)",
              }}
            >
              <label
                style={{
                  display: "flex",
                  gap: 8,
                  alignItems: "flex-start",
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                <input
                  type="checkbox"
                  checked={tagForm.is_exclusive_combination}
                  onChange={(e) =>
                    setTagForm({
                      ...tagForm,
                      is_exclusive_combination: e.target.checked,
                    })
                  }
                  style={{ marginTop: 3 }}
                />
                <span>
                  <strong>Etiqueta única en todas sus combinaciones</strong>
                  <div
                    style={{ marginTop: 4, opacity: 0.75, lineHeight: 1.5 }}
                  >
                    Si está marcada, la combinación de esta etiqueta con cada
                    etiqueta que el escenario tenga en otras categorías debe
                    ser única entre todos los escenarios. Ejemplo: solo un
                    escenario puede ser «Oficial + PA». Intentar asignarla a
                    otro escenario que comparta la misma combinación disparará
                    una confirmación para transferirla (y quitársela al
                    escenario anterior). Si el escenario no tiene etiquetas en
                    otras categorías, varios escenarios pueden compartir esta
                    etiqueta sin conflicto.
                  </div>
                </span>
              </label>
            </div>
          </div>
        ) : null}
      </Modal>

      <ConfirmDialog
        open={categoryToDelete !== null}
        title="Eliminar categoría"
        message={
          <>
            ¿Eliminar la categoría{" "}
            <strong>{categoryToDelete?.name}</strong>? No se puede eliminar si
            tiene etiquetas asignadas.
          </>
        }
        danger
        confirmLabel="Eliminar"
        onConfirm={confirmDeleteCategory}
        onCancel={() => setCategoryToDelete(null)}
      />
      <ConfirmDialog
        open={tagToDelete !== null}
        title="Eliminar etiqueta"
        message={
          <>
            ¿Eliminar la etiqueta <strong>{tagToDelete?.name}</strong>? Esto la
            quitará de todos los escenarios que la tengan.
          </>
        }
        danger
        confirmLabel="Eliminar"
        onConfirm={confirmDeleteTag}
        onCancel={() => setTagToDelete(null)}
      />
    </div>
  );
}

function ColorSwatch({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label style={{ fontSize: 13, display: "block", marginBottom: 4 }}>
        Color
      </label>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
        {COLOR_PALETTE.map((hex) => {
          const active = hex.toLowerCase() === value.toLowerCase();
          return (
            <button
              key={hex}
              type="button"
              onClick={() => onChange(hex)}
              style={{
                width: 26,
                height: 26,
                borderRadius: 6,
                background: hex,
                border: active
                  ? "2px solid #fff"
                  : "1px solid rgba(255,255,255,0.2)",
                cursor: "pointer",
                padding: 0,
              }}
              title={hex}
              aria-label={`Seleccionar color ${hex}`}
            />
          );
        })}
        <input
          type="color"
          value={value}
          onChange={(e) => onChange(e.target.value.toUpperCase())}
          style={{
            width: 36,
            height: 26,
            border: "1px solid rgba(255,255,255,0.2)",
            borderRadius: 6,
            background: "transparent",
            cursor: "pointer",
          }}
        />
      </div>
    </div>
  );
}
