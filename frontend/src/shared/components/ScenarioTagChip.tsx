/**
 * Chip coloreado con el nombre de una etiqueta de escenario.
 *
 * Si se pasa `onRemove`, muestra una "×" al hacer hover sobre el chip; al
 * clicarla dispara la confirmación (el parent debe mostrar el diálogo y
 * luego invocar `onRemove`).
 */
import { useState } from "react";

import type { ScenarioTag } from "@/types/domain";

type Props = {
  tag: ScenarioTag;
  onRemove?: (() => void) | undefined;
  size?: "sm" | "md";
  /** Muestra el nombre de la categoría arriba del tag, útil en el detalle. */
  showCategory?: boolean;
};

export function ScenarioTagChip({ tag, onRemove, size = "md", showCategory = false }: Props) {
  const padX = size === "sm" ? 6 : 8;
  const padY = size === "sm" ? 1 : 2;
  const fontSize = size === "sm" ? 11 : 12;
  const [hover, setHover] = useState(false);
  const removable = Boolean(onRemove);

  return (
    <span
      onMouseEnter={removable ? () => setHover(true) : undefined}
      onMouseLeave={removable ? () => setHover(false) : undefined}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: `${padY}px ${padX}px`,
        borderRadius: 6,
        fontSize,
        fontWeight: 600,
        backgroundColor: tag.color,
        color: "#fff",
        textShadow: "0 0 1px rgba(0,0,0,0.6)",
        maxWidth: "100%",
      }}
      title={
        showCategory && tag.category
          ? `${tag.category.name}: ${tag.name}`
          : tag.name
      }
    >
      <span
        style={{
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {tag.name.trim().toLowerCase() === "oficial" ? "★ " : ""}
        {tag.name}
      </span>
      {removable ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRemove?.();
          }}
          aria-label={`Quitar etiqueta ${tag.name}`}
          title={`Quitar etiqueta ${tag.name}`}
          style={{
            marginLeft: 2,
            background: "rgba(0,0,0,0.25)",
            border: "none",
            color: "inherit",
            fontSize: fontSize + 2,
            lineHeight: 1,
            width: hover ? 16 : 0,
            height: 16,
            borderRadius: 3,
            cursor: "pointer",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 0,
            opacity: hover ? 1 : 0,
            overflow: "hidden",
            transition: "width 120ms ease, opacity 120ms ease",
            pointerEvents: hover ? "auto" : "none",
          }}
        >
          ×
        </button>
      ) : null}
    </span>
  );
}
