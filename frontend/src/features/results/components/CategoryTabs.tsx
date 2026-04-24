/**
 * Pestañas de categorías del Data Explorer en dos filas:
 *  - Fila 1: categoría madre (siempre visible).
 *  - Fila 2: subcategorías de la madre activa (si tiene).
 */
import type { Category, SubCategory } from "@/features/results/categories";

type Props = {
  categories: Category[];
  activeCategory: string | null;
  activeSubCategory: string | null;
  onSelectCategory: (cat: Category) => void;
  onSelectSubCategory: (cat: Category, sub: SubCategory) => void;
  /** Variables disponibles para el contexto filtrado (desde facets). */
  variableOptions?: string[] | undefined;
  /** Variable seleccionada (única); null = "Todas". */
  activeVariable?: string | null | undefined;
  onSelectVariable?: ((variable: string | null) => void) | undefined;
};

const ROW_STYLE = {
  display: "flex",
  gap: 6,
  flexWrap: "wrap" as const,
  alignItems: "center",
};

function pillStyle(active: boolean, level: 1 | 2): React.CSSProperties {
  const fontSize = level === 1 ? 13 : 12;
  const padding = level === 1 ? "6px 12px" : "4px 10px";
  return {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    fontSize,
    padding,
    borderRadius: 999,
    cursor: "pointer",
    whiteSpace: "nowrap",
    border: active
      ? "1px solid rgba(80,140,255,0.55)"
      : "1px solid rgba(255,255,255,0.12)",
    background: active
      ? "rgba(80,140,255,0.18)"
      : "rgba(255,255,255,0.03)",
    color: active ? "rgba(220,230,255,0.95)" : "var(--muted)",
    transition: "background 120ms ease, border-color 120ms ease",
  };
}

export function CategoryTabs({
  categories,
  activeCategory,
  activeSubCategory,
  onSelectCategory,
  onSelectSubCategory,
  variableOptions,
  activeVariable,
  onSelectVariable,
}: Props) {
  const active = categories.find((c) => c.id === activeCategory) ?? null;
  const showVariableRow =
    onSelectVariable !== undefined &&
    variableOptions !== undefined &&
    variableOptions.length > 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={ROW_STYLE} role="tablist" aria-label="Categorías">
        {categories.map((cat) => {
          const isActive = cat.id === activeCategory;
          return (
            <button
              key={cat.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => onSelectCategory(cat)}
              title={
                cat.id === "todos"
                  ? "Limpiar todos los filtros"
                  : `Aplicar filtros de "${cat.label}" (sobrescribe tu selección manual)`
              }
              style={pillStyle(isActive, 1)}
            >
              {cat.icon ? <span>{cat.icon}</span> : null}
              {cat.label}
            </button>
          );
        })}
      </div>

      {active?.sub && active.sub.length > 0 ? (
        <div
          style={{
            ...ROW_STYLE,
            padding: "4px 0 2px 16px",
            borderLeft: "2px solid rgba(80,140,255,0.35)",
          }}
          role="tablist"
          aria-label={`Subcategorías de ${active.label}`}
        >
          {active.sub.map((sub) => {
            const isActive = sub.id === activeSubCategory;
            return (
              <button
                key={sub.id}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => onSelectSubCategory(active, sub)}
                title={`Aplicar filtros de "${sub.label}"`}
                style={pillStyle(isActive, 2)}
              >
                {sub.icon ? <span>{sub.icon}</span> : null}
                {sub.label}
              </button>
            );
          })}
        </div>
      ) : null}

      {showVariableRow ? (
        <div
          style={{
            ...ROW_STYLE,
            padding: "4px 0 2px 32px",
            borderLeft: "2px solid rgba(80,140,255,0.18)",
          }}
          role="tablist"
          aria-label="Variable"
        >
          <span style={{ fontSize: 11, opacity: 0.55, marginRight: 4 }}>Variable:</span>
          <button
            type="button"
            role="tab"
            aria-selected={activeVariable == null}
            onClick={() => onSelectVariable?.(null)}
            title="Mostrar todas las variables disponibles"
            style={pillStyle(activeVariable == null, 2)}
          >
            Todas
          </button>
          {variableOptions!.map((v) => {
            const isActive = activeVariable === v;
            return (
              <button
                key={v}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => onSelectVariable?.(v)}
                title={`Filtrar a variable ${v}`}
                style={pillStyle(isActive, 2)}
              >
                {v}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
