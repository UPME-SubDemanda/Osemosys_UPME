/**
 * Badge/etiqueta con variantes de color para estados (éxito, error, advertencia, etc.).
 * Usado para mostrar estados de escenarios, solicitudes de cambio, simulaciones, etc.
 */
import type { ReactNode } from "react";

type Variant = "neutral" | "success" | "warning" | "danger" | "info";

/** Mapa de estilos por variante (fondo y borde) */
const colors: Record<Variant, React.CSSProperties> = {
  neutral: { background: "rgba(148,163,184,0.14)", border: "1px solid rgba(148,163,184,0.3)" },
  success: { background: "rgba(34,197,94,0.14)", border: "1px solid rgba(34,197,94,0.34)" },
  warning: { background: "rgba(245,158,11,0.14)", border: "1px solid rgba(245,158,11,0.34)" },
  danger: { background: "rgba(239,68,68,0.14)", border: "1px solid rgba(239,68,68,0.34)" },
  info: { background: "rgba(56,189,248,0.14)", border: "1px solid rgba(56,189,248,0.34)" },
};

export function Badge({ children, variant = "neutral" }: { children: ReactNode; variant?: Variant }) {
  return (
    <span
      style={{
        ...colors[variant],
        borderRadius: 999,
        padding: "4px 10px",
        fontSize: 12,
        fontWeight: 600,
        display: "inline-flex",
        alignItems: "center",
      }}
    >
      {children}
    </span>
  );
}

