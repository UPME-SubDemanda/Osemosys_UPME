/**
 * Editor compartido de la organización del reporte (categorías + subcategorías + gráficas).
 *
 * Lo usan tanto el "Generador de reporte" como el modo "Editar organización"
 * del dashboard, con la misma funcionalidad:
 *   - Renombrar categorías y subcategorías inline.
 *   - Crear nuevas categorías y subcategorías.
 *   - Eliminar categorías/subcategorías (los items huérfanos van a "Sin asignar").
 *   - Agregar gráficas accesibles que aún no estén en el reporte.
 *   - Mover gráficas entre categorías y subcategorías.
 *   - Reordenar gráficas (↑ ↓) dentro de su contenedor.
 *   - Quitar una gráfica del reporte (× rojo).
 *
 * El parent maneja la persistencia (guardar el reporte, PATCH `/saved-reports`).
 */
import { useMemo, useState } from "react";
import type {
  ReportLayout,
  ReportLayoutCategory,
  ReportLayoutSubcategory,
  SavedChartTemplate,
} from "@/types/domain";

type Props = {
  layout: ReportLayout;
  onLayoutChange: (next: ReportLayout) => void;
  /** Items del reporte (lista plana ordenada). Se mantiene en sync con el layout. */
  items: number[];
  onItemsChange: (next: number[]) => void;
  /** Plantillas referenciables (incluye propias y públicas). */
  accessibleTemplates: SavedChartTemplate[];
};

function moveItemInArray(arr: number[], index: number, delta: -1 | 1): number[] {
  const next = [...arr];
  const target = index + delta;
  if (target < 0 || target >= next.length) return arr;
  const tmp = next[index]!;
  next[index] = next[target]!;
  next[target] = tmp;
  return next;
}

function withItemRemovedEverywhere(
  layout: ReportLayout,
  itemId: number,
): ReportLayout {
  return {
    categories: layout.categories.map((c) => ({
      ...c,
      items: c.items.filter((id) => id !== itemId),
      subcategories: c.subcategories.map((s) => ({
        ...s,
        items: s.items.filter((id) => id !== itemId),
      })),
    })),
  };
}

export function CategoriesPanel({
  layout,
  onLayoutChange,
  items,
  onItemsChange,
  accessibleTemplates,
}: Props) {
  const [pickerOpenForCat, setPickerOpenForCat] = useState<string | null>(null);
  const [pickerOpenForSub, setPickerOpenForSub] = useState<{
    catId: string;
    subId: string;
  } | null>(null);

  const templatesById = useMemo(
    () => new Map(accessibleTemplates.map((t) => [t.id, t])),
    [accessibleTemplates],
  );

  const itemsInLayout = useMemo(() => {
    const set = new Set<number>();
    for (const c of layout.categories) {
      c.items.forEach((id) => set.add(id));
      for (const s of c.subcategories) s.items.forEach((id) => set.add(id));
    }
    return set;
  }, [layout]);

  const availableForPicker = useMemo(
    () => accessibleTemplates.filter((t) => !itemsInLayout.has(t.id)),
    [accessibleTemplates, itemsInLayout],
  );

  // ── Mutaciones de categorías/subcategorías ──
  const renameCategory = (id: string, label: string) => {
    onLayoutChange({
      categories: layout.categories.map((c) =>
        c.id === id ? { ...c, label } : c,
      ),
    });
  };
  const renameSub = (catId: string, subId: string, label: string) => {
    onLayoutChange({
      categories: layout.categories.map((c) =>
        c.id === catId
          ? {
              ...c,
              subcategories: c.subcategories.map((s) =>
                s.id === subId ? { ...s, label } : s,
              ),
            }
          : c,
      ),
    });
  };
  const addSubcategory = (catId: string) => {
    onLayoutChange({
      categories: layout.categories.map((c) =>
        c.id === catId
          ? {
              ...c,
              subcategories: [
                ...c.subcategories,
                {
                  id: `sub_${Date.now()}`,
                  label: "Nueva subcategoría",
                  items: [],
                },
              ],
            }
          : c,
      ),
    });
  };
  const addCategory = () => {
    onLayoutChange({
      categories: [
        ...layout.categories,
        {
          id: `custom_${Date.now()}`,
          label: "Nueva categoría",
          items: [],
          subcategories: [],
        },
      ],
    });
  };
  const removeCategory = (id: string) => {
    const cat = layout.categories.find((c) => c.id === id);
    if (!cat) return;
    const orphaned = [
      ...cat.items,
      ...cat.subcategories.flatMap((s) => s.items),
    ];
    const remaining = layout.categories.filter((c) => c.id !== id);
    if (orphaned.length === 0) {
      onLayoutChange({ categories: remaining });
      return;
    }
    const idx = remaining.findIndex((c) => c.id === "_unassigned");
    if (idx >= 0) {
      const u = remaining[idx]!;
      remaining[idx] = { ...u, items: [...u.items, ...orphaned] };
    } else {
      remaining.push({
        id: "_unassigned",
        label: "Sin asignar",
        items: orphaned,
        subcategories: [],
      });
    }
    onLayoutChange({ categories: remaining });
  };
  const removeSub = (catId: string, subId: string) => {
    onLayoutChange({
      categories: layout.categories.map((c) => {
        if (c.id !== catId) return c;
        const sub = c.subcategories.find((s) => s.id === subId);
        const orphaned = sub?.items ?? [];
        return {
          ...c,
          items: [...c.items, ...orphaned],
          subcategories: c.subcategories.filter((s) => s.id !== subId),
        };
      }),
    });
  };

  // ── Mutaciones de items ──
  const moveItemTo = (
    itemId: number,
    target: { catId: string; subId?: string },
  ) => {
    const stripped = withItemRemovedEverywhere(layout, itemId);
    const next: ReportLayoutCategory[] = stripped.categories.map((c) => {
      if (c.id !== target.catId) return c;
      if (target.subId) {
        return {
          ...c,
          subcategories: c.subcategories.map((s) =>
            s.id === target.subId ? { ...s, items: [...s.items, itemId] } : s,
          ),
        };
      }
      return { ...c, items: [...c.items, itemId] };
    });
    onLayoutChange({ categories: next });
  };

  const reorderInCategory = (
    catId: string,
    index: number,
    delta: -1 | 1,
  ) => {
    onLayoutChange({
      categories: layout.categories.map((c) =>
        c.id === catId
          ? { ...c, items: moveItemInArray(c.items, index, delta) }
          : c,
      ),
    });
  };
  const reorderInSub = (
    catId: string,
    subId: string,
    index: number,
    delta: -1 | 1,
  ) => {
    onLayoutChange({
      categories: layout.categories.map((c) =>
        c.id === catId
          ? {
              ...c,
              subcategories: c.subcategories.map((s) =>
                s.id === subId
                  ? { ...s, items: moveItemInArray(s.items, index, delta) }
                  : s,
              ),
            }
          : c,
      ),
    });
  };

  const removeItem = (itemId: number) => {
    onLayoutChange(withItemRemovedEverywhere(layout, itemId));
    onItemsChange(items.filter((id) => id !== itemId));
  };

  const addItem = (
    chartId: number,
    target: { catId: string; subId?: string },
  ) => {
    if (items.includes(chartId)) {
      // Ya está en el reporte; solo movemos.
      moveItemTo(chartId, target);
      return;
    }
    onItemsChange([...items, chartId]);
    const stripped = withItemRemovedEverywhere(layout, chartId);
    const next: ReportLayoutCategory[] = stripped.categories.map((c) => {
      if (c.id !== target.catId) return c;
      if (target.subId) {
        return {
          ...c,
          subcategories: c.subcategories.map((s) =>
            s.id === target.subId ? { ...s, items: [...s.items, chartId] } : s,
          ),
        };
      }
      return { ...c, items: [...c.items, chartId] };
    });
    onLayoutChange({ categories: next });
    setPickerOpenForCat(null);
    setPickerOpenForSub(null);
  };

  const subcategoryDisplay = layout.subcategory_display ?? "tabs";
  const setSubcategoryDisplay = (mode: "tabs" | "accordions") => {
    onLayoutChange({ ...layout, subcategory_display: mode });
  };

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Subcategorías en el dashboard:
            </span>
            <div
              role="group"
              aria-label="Modo de subcategorías en el dashboard"
              className="inline-flex rounded-lg border border-slate-700 bg-slate-900/60 p-0.5"
            >
              <button
                type="button"
                onClick={() => setSubcategoryDisplay("tabs")}
                className={`rounded-md px-2.5 py-1 text-[11px] font-semibold ${
                  subcategoryDisplay === "tabs"
                    ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/25"
                    : "text-slate-400"
                }`}
                title="En el dashboard, las subcategorías serán pestañas (una visible)"
              >
                Pestañas
              </button>
              <button
                type="button"
                onClick={() => setSubcategoryDisplay("accordions")}
                className={`rounded-md px-2.5 py-1 text-[11px] font-semibold ${
                  subcategoryDisplay === "accordions"
                    ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/25"
                    : "text-slate-400"
                }`}
                title="En el dashboard, las subcategorías serán acordeones apilados verticalmente"
              >
                Acordeones
              </button>
            </div>
          </div>
          <p className="m-0 text-[10px] text-slate-500 italic">
            Esta opción solo afecta cómo se mostrarán las subcategorías al
            visualizar el dashboard del reporte. No cambia esta vista del
            generador.
          </p>
        </div>
      </div>
      {layout.categories.map((cat) => (
        <CategoryCard
          key={cat.id}
          cat={cat}
          allCategories={layout.categories}
          templatesById={templatesById}
          availableForPicker={availableForPicker}
          pickerOpenForCat={pickerOpenForCat}
          pickerOpenForSub={pickerOpenForSub}
          setPickerOpenForCat={setPickerOpenForCat}
          setPickerOpenForSub={setPickerOpenForSub}
          renameCategory={renameCategory}
          renameSub={renameSub}
          addSubcategory={addSubcategory}
          removeCategory={removeCategory}
          removeSub={removeSub}
          moveItemTo={moveItemTo}
          reorderInCategory={reorderInCategory}
          reorderInSub={reorderInSub}
          removeItem={removeItem}
          addItem={addItem}
        />
      ))}
      <button
        type="button"
        onClick={addCategory}
        className="rounded-lg border border-dashed border-cyan-500/40 px-4 py-2 text-xs font-semibold text-cyan-300 hover:bg-cyan-500/10"
      >
        + Nueva categoría
      </button>
    </div>
  );
}

// ─── Sub-componente: tarjeta de categoría ───────────────────────────────────

type CategoryCardProps = {
  cat: ReportLayoutCategory;
  allCategories: ReportLayoutCategory[];
  templatesById: Map<number, SavedChartTemplate>;
  availableForPicker: SavedChartTemplate[];
  pickerOpenForCat: string | null;
  pickerOpenForSub: { catId: string; subId: string } | null;
  setPickerOpenForCat: (v: string | null) => void;
  setPickerOpenForSub: (v: { catId: string; subId: string } | null) => void;
  renameCategory: (id: string, label: string) => void;
  renameSub: (catId: string, subId: string, label: string) => void;
  addSubcategory: (catId: string) => void;
  removeCategory: (id: string) => void;
  removeSub: (catId: string, subId: string) => void;
  moveItemTo: (
    itemId: number,
    target: { catId: string; subId?: string },
  ) => void;
  reorderInCategory: (catId: string, index: number, delta: -1 | 1) => void;
  reorderInSub: (
    catId: string,
    subId: string,
    index: number,
    delta: -1 | 1,
  ) => void;
  removeItem: (id: number) => void;
  addItem: (chartId: number, target: { catId: string; subId?: string }) => void;
};

function CategoryCard({
  cat,
  allCategories,
  templatesById,
  availableForPicker,
  pickerOpenForCat,
  pickerOpenForSub,
  setPickerOpenForCat,
  setPickerOpenForSub,
  renameCategory,
  renameSub,
  addSubcategory,
  removeCategory,
  removeSub,
  moveItemTo,
  reorderInCategory,
  reorderInSub,
  removeItem,
  addItem,
}: CategoryCardProps) {
  const totalItems =
    cat.items.length +
    cat.subcategories.reduce((acc, s) => acc + s.items.length, 0);
  const isPickerOpen = pickerOpenForCat === cat.id;
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 space-y-3">
      {/* Header categoría */}
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="text"
          value={cat.label}
          onChange={(e) => renameCategory(cat.id, e.target.value)}
          className="rounded-md border border-slate-700 bg-slate-950/50 px-2 py-1 text-sm font-semibold text-white"
        />
        <span className="text-[11px] text-slate-500">
          {totalItems} gráfica{totalItems === 1 ? "" : "s"}
        </span>
        <div className="ml-auto flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => addSubcategory(cat.id)}
            className="rounded-md border border-slate-700 px-2 py-1 text-[11px] text-slate-300 hover:bg-slate-800"
          >
            + Subcategoría
          </button>
          <button
            type="button"
            onClick={() =>
              setPickerOpenForCat(isPickerOpen ? null : cat.id)
            }
            className="rounded-md border border-cyan-500/40 px-2 py-1 text-[11px] text-cyan-300 hover:bg-cyan-500/10"
          >
            + Agregar gráfica
          </button>
          <button
            type="button"
            onClick={() => removeCategory(cat.id)}
            className="rounded-md border border-rose-500/40 px-2 py-1 text-[11px] text-rose-300 hover:bg-rose-500/10"
          >
            Eliminar categoría
          </button>
        </div>
      </div>

      {/* Picker de gráficas para añadir a la categoría */}
      {isPickerOpen ? (
        <ChartPicker
          templates={availableForPicker}
          onPick={(id) => addItem(id, { catId: cat.id })}
          onClose={() => setPickerOpenForCat(null)}
        />
      ) : null}

      {/* Items directos */}
      {cat.items.length > 0 ? (
        <ul className="grid gap-1.5 list-none p-0 m-0">
          {cat.items.map((id, idx) => {
            const tpl = templatesById.get(id);
            if (!tpl) return null;
            return (
              <ItemRow
                key={id}
                tpl={tpl}
                allCategories={allCategories}
                currentCatId={cat.id}
                onMoveUp={() =>
                  reorderInCategory(cat.id, idx, -1)
                }
                onMoveDown={() =>
                  reorderInCategory(cat.id, idx, 1)
                }
                isFirst={idx === 0}
                isLast={idx === cat.items.length - 1}
                onMoveTo={(target) => moveItemTo(id, target)}
                onRemove={() => removeItem(id)}
              />
            );
          })}
        </ul>
      ) : null}

      {/* Subcategorías */}
      {cat.subcategories.map((sub) => {
        const subPickerOpen =
          pickerOpenForSub != null &&
          pickerOpenForSub.catId === cat.id &&
          pickerOpenForSub.subId === sub.id;
        return (
          <div
            key={sub.id}
            className="rounded-md border border-slate-800/70 bg-slate-950/30 p-2 space-y-2"
          >
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="text"
                value={sub.label}
                onChange={(e) => renameSub(cat.id, sub.id, e.target.value)}
                className="rounded border border-slate-700 bg-slate-950/50 px-2 py-0.5 text-xs font-semibold text-slate-200"
              />
              <span className="text-[10px] text-slate-500">
                {sub.items.length} gráficas
              </span>
              <div className="ml-auto flex gap-2">
                <button
                  type="button"
                  onClick={() =>
                    setPickerOpenForSub(
                      subPickerOpen ? null : { catId: cat.id, subId: sub.id },
                    )
                  }
                  className="rounded-md border border-cyan-500/40 px-2 py-0.5 text-[10px] text-cyan-300 hover:bg-cyan-500/10"
                >
                  + Agregar gráfica
                </button>
                <button
                  type="button"
                  onClick={() => removeSub(cat.id, sub.id)}
                  className="rounded-md border border-rose-500/40 px-2 py-0.5 text-[10px] text-rose-300 hover:bg-rose-500/10"
                >
                  Eliminar
                </button>
              </div>
            </div>
            {subPickerOpen ? (
              <ChartPicker
                templates={availableForPicker}
                onPick={(id) =>
                  addItem(id, { catId: cat.id, subId: sub.id })
                }
                onClose={() => setPickerOpenForSub(null)}
                compact
              />
            ) : null}
            {sub.items.length > 0 ? (
              <ul className="grid gap-1 list-none p-0 m-0">
                {sub.items.map((id, idx) => {
                  const tpl = templatesById.get(id);
                  if (!tpl) return null;
                  return (
                    <ItemRow
                      key={id}
                      tpl={tpl}
                      allCategories={allCategories}
                      currentCatId={cat.id}
                      currentSubId={sub.id}
                      onMoveUp={() =>
                        reorderInSub(cat.id, sub.id, idx, -1)
                      }
                      onMoveDown={() =>
                        reorderInSub(cat.id, sub.id, idx, 1)
                      }
                      isFirst={idx === 0}
                      isLast={idx === sub.items.length - 1}
                      onMoveTo={(target) => moveItemTo(id, target)}
                      onRemove={() => removeItem(id)}
                      compact
                    />
                  );
                })}
              </ul>
            ) : (
              <p className="m-0 text-[10px] text-slate-600">
                Sin gráficas. Mueve alguna desde otra categoría o usa "+ Agregar
                gráfica".
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Sub-componente: fila de un chart con controles ─────────────────────────

type ItemRowProps = {
  tpl: SavedChartTemplate;
  allCategories: ReportLayoutCategory[];
  currentCatId: string;
  currentSubId?: string | undefined;
  onMoveUp: () => void;
  onMoveDown: () => void;
  isFirst: boolean;
  isLast: boolean;
  onMoveTo: (target: { catId: string; subId?: string }) => void;
  onRemove: () => void;
  compact?: boolean;
};

function ItemRow({
  tpl,
  allCategories,
  currentCatId,
  currentSubId,
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
  onMoveTo,
  onRemove,
  compact,
}: ItemRowProps) {
  const cls = compact
    ? "flex flex-wrap items-center gap-2 rounded border border-slate-800 bg-slate-950/40 p-1.5 text-[11px]"
    : "flex flex-wrap items-center gap-2 rounded-md border border-slate-800 bg-slate-950/40 p-2 text-xs";
  const btnSize = compact ? "h-6 w-6 text-[10px]" : "h-7 w-7 text-xs";
  const inputCls = compact
    ? "rounded-md border border-slate-700 bg-slate-950/50 px-2 py-0.5 text-[10px] text-slate-200"
    : "rounded-md border border-slate-700 bg-slate-950/50 px-2 py-1 text-[11px] text-slate-200";

  return (
    <li className={cls}>
      <div className="flex shrink-0 gap-0.5">
        <button
          type="button"
          onClick={onMoveUp}
          disabled={isFirst}
          title="Subir"
          className={`inline-flex items-center justify-center rounded border border-slate-700 text-slate-300 hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed ${btnSize}`}
        >
          ↑
        </button>
        <button
          type="button"
          onClick={onMoveDown}
          disabled={isLast}
          title="Bajar"
          className={`inline-flex items-center justify-center rounded border border-slate-700 text-slate-300 hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed ${btnSize}`}
        >
          ↓
        </button>
      </div>
      <span className="min-w-0 flex-1 truncate text-slate-200">{tpl.name}</span>
      <select
        value=""
        onChange={(e) => {
          const v = e.target.value;
          if (v.startsWith("cat:")) onMoveTo({ catId: v.slice(4) });
          else if (v.startsWith("sub:")) {
            const [catId, subId] = v.slice(4).split("::");
            if (catId && subId) onMoveTo({ catId, subId });
          }
        }}
        className={inputCls}
      >
        <option value="">Mover a…</option>
        {allCategories.map((c) => (
          <optgroup key={c.id} label={c.label}>
            {!(c.id === currentCatId && !currentSubId) ? (
              <option value={`cat:${c.id}`}>{c.label} (categoría)</option>
            ) : null}
            {c.subcategories
              .filter(
                (s) => !(c.id === currentCatId && s.id === currentSubId),
              )
              .map((s) => (
                <option key={s.id} value={`sub:${c.id}::${s.id}`}>
                  {c.label} → {s.label}
                </option>
              ))}
          </optgroup>
        ))}
      </select>
      <button
        type="button"
        onClick={onRemove}
        title="Quitar del reporte"
        className={`inline-flex items-center justify-center rounded border border-rose-500/40 text-rose-300 hover:bg-rose-500/10 ${btnSize}`}
      >
        ×
      </button>
    </li>
  );
}

// ─── Sub-componente: picker de gráficas accesibles ──────────────────────────

export function ChartPicker({
  templates,
  onPick,
  onClose,
  compact,
  currentItemIds,
}: {
  templates: SavedChartTemplate[];
  onPick: (id: number) => void;
  onClose: () => void;
  compact?: boolean;
  /** Si se provee, muestra "ya en reporte" sobre las plantillas listadas. */
  currentItemIds?: number[];
}) {
  const [filter, setFilter] = useState("");
  const inReportSet = useMemo(
    () => new Set(currentItemIds ?? []),
    [currentItemIds],
  );
  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return templates;
    return templates.filter((t) => t.name.toLowerCase().includes(q));
  }, [templates, filter]);

  const cls = compact
    ? "rounded border border-cyan-500/30 bg-cyan-500/5 p-2 space-y-2"
    : "rounded-lg border border-cyan-500/30 bg-cyan-500/5 p-3 space-y-2";

  return (
    <div className={cls}>
      <div className="flex items-center gap-2">
        <input
          type="text"
          placeholder="Buscar gráficas accesibles…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="flex-1 rounded border border-slate-700 bg-slate-950/50 px-2 py-1 text-xs text-slate-200"
        />
        <button
          type="button"
          onClick={onClose}
          className="rounded border border-slate-700 px-2 py-1 text-[11px] text-slate-400 hover:bg-slate-800"
        >
          Cerrar
        </button>
      </div>
      {filtered.length === 0 ? (
        <p className="m-0 text-[11px] text-slate-500">
          {templates.length === 0
            ? "No tienes gráficas guardadas accesibles."
            : "Sin coincidencias."}
        </p>
      ) : (
        <ul className="grid gap-1 max-h-64 overflow-y-auto list-none p-0 m-0">
          {filtered.slice(0, 100).map((t) => {
            const inReport = inReportSet.has(t.id);
            return (
              <li key={t.id}>
                <button
                  type="button"
                  onClick={() => onPick(t.id)}
                  className="w-full rounded border border-slate-800 bg-slate-950/40 px-2 py-1 text-left text-[11px] text-slate-200 hover:bg-cyan-500/10 hover:border-cyan-500/40"
                  title={
                    inReport
                      ? "Ya está en el reporte; al elegirla la moverás a esta sección"
                      : t.is_owner
                        ? "tu gráfica"
                        : `de ${t.owner_username ?? "otro"}`
                  }
                >
                  {t.name}
                  {!t.is_owner ? (
                    <span className="ml-1 text-[10px] text-slate-500">
                      · de {t.owner_username ?? "otro"}
                    </span>
                  ) : null}
                  {inReport ? (
                    <span className="ml-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-amber-300">
                      ya en reporte · mover
                    </span>
                  ) : null}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
