import type { ScenarioTag } from "@/types/domain";

/** Chip de nombre con color de la etiqueta de escenario. */
export function ScenarioTagChip({ tag }: { tag: ScenarioTag }) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: 6,
        fontSize: 12,
        fontWeight: 600,
        backgroundColor: tag.color,
        color: "#fff",
        textShadow: "0 0 1px rgba(0,0,0,0.6)",
        maxWidth: "100%",
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
      }}
      title={tag.name}
    >
      {tag.name}
    </span>
  );
}
