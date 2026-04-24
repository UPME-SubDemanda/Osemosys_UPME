/**
 * Página admin del catálogo editable de visualización (Fase 3.3).
 *
 * Tabs planeados (uno por sub-fase):
 *   3.3.A — Colores (implementado)
 *   3.3.B — Etiquetas (stub)
 *   3.3.C — Taxonomía: sectores + familias (stub)
 *   3.3.D — Módulos del selector de gráficas (stub)
 *   3.3.E — Unidades (stub)
 *   3.3.F — Gráficas: configuración lógica (stub)
 *   3.3.G — Gráficas: configuración estética (stub)
 *   3.3.H — Sub-filtros (stub)
 *
 * Acceso restringido: requiere `can_manage_catalogs`.
 */
import { useState } from "react";
import { ChartsTab } from "@/features/catalogMeta/components/ChartsTab";
import { ColorsTab } from "@/features/catalogMeta/components/ColorsTab";
import { LabelsTab } from "@/features/catalogMeta/components/LabelsTab";
import { ModulesTab } from "@/features/catalogMeta/components/ModulesTab";
import { UnitsTab } from "@/features/catalogMeta/components/UnitsTab";

type TabKey =
  | "colors"
  | "labels"
  | "modules"
  | "units"
  | "charts"
  | "aesthetic"
  | "subfilters";

type Tab = {
  key: TabKey;
  label: string;
  icon: string;
  phase: string;
  enabled: boolean;
};

// Las pestañas deshabilitadas NO se muestran en la UI (prod mode).
// Para reactivar, poner enabled=true.
const TABS: Tab[] = [
  { key: "colors",     label: "Colores",   icon: "🎨", phase: "3.3.A", enabled: true  },
  { key: "labels",     label: "Etiquetas", icon: "🏷️", phase: "3.3.B", enabled: true  },
  { key: "modules",    label: "Módulos",   icon: "📂", phase: "3.3.D", enabled: false },
  { key: "units",      label: "Unidades",  icon: "📏", phase: "3.3.E", enabled: true  },
  { key: "charts",     label: "Gráficas",  icon: "📊", phase: "3.3.F", enabled: false },
  { key: "aesthetic",  label: "Estética",  icon: "✨", phase: "3.3.G", enabled: false },
  { key: "subfilters", label: "Sub-filtros", icon: "🔍", phase: "3.3.H", enabled: false },
];

export function VisualizationCatalogAdminPage() {
  const [active, setActive] = useState<TabKey>("colors");

  return (
    <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 14 }}>
      <div>
        <h2 style={{ margin: 0, fontSize: 20 }}>Catálogo de visualización</h2>
        <p style={{ margin: "4px 0 0", fontSize: 12, opacity: 0.7 }}>
          Configuración editable de colores, etiquetas, sectores, módulos, gráficas
          y sub-filtros. Los cambios se propagan a todos los workers tras 30 s como
          máximo.
        </p>
      </div>

      <div
        style={{
          display: "flex",
          gap: 6,
          flexWrap: "wrap",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          paddingBottom: 10,
        }}
      >
        {TABS.filter((t) => t.enabled).map((t) => {
          const isActive = t.key === active;
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => t.enabled && setActive(t.key)}
              disabled={!t.enabled}
              title={t.enabled ? t.label : `${t.label} — pendiente (${t.phase})`}
              style={{
                fontSize: 13,
                padding: "6px 12px",
                borderRadius: 8,
                cursor: t.enabled ? "pointer" : "not-allowed",
                border: isActive
                  ? "1px solid rgba(80,140,255,0.55)"
                  : "1px solid rgba(255,255,255,0.1)",
                background: isActive
                  ? "rgba(80,140,255,0.18)"
                  : "transparent",
                color: isActive
                  ? "rgba(220,230,255,0.95)"
                  : t.enabled
                    ? "var(--muted)"
                    : "rgba(255,255,255,0.25)",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <span>{t.icon}</span>
              {t.label}
              {!t.enabled ? (
                <span style={{ fontSize: 10, opacity: 0.5 }}>({t.phase})</span>
              ) : null}
            </button>
          );
        })}
      </div>

      <div>
        {active === "colors" ? <ColorsTab /> : null}
        {active === "labels" ? <LabelsTab /> : null}
        {active === "modules" ? <ModulesTab /> : null}
        {active === "units" ? <UnitsTab /> : null}
        {active === "charts" ? <ChartsTab /> : null}
      </div>
    </div>
  );
}

export default VisualizationCatalogAdminPage;
