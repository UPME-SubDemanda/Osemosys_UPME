/**
 * Botón-estrella para marcar/desmarcar un resultado como favorito del usuario
 * actual. Llama al endpoint `PATCH /simulations/{id}/favorite` y notifica al
 * padre con `onToggled(isFavorite)`.
 */
import { useState } from "react";
import { simulationApi } from "@/features/simulation/api/simulationApi";

type Props = {
  jobId: number;
  isFavorite: boolean;
  onToggled?: (next: boolean) => void;
  size?: number;
  title?: string;
};

export function FavoriteStarButton({
  jobId,
  isFavorite,
  onToggled,
  size = 18,
  title,
}: Props) {
  const [saving, setSaving] = useState(false);

  const handleClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    if (saving) return;
    const next = !isFavorite;
    setSaving(true);
    try {
      await simulationApi.setFavorite(jobId, next);
      onToggled?.(next);
    } catch (err) {
      console.error("Error toggling favorite", err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={saving}
      title={
        title ??
        (isFavorite ? "Quitar de favoritos" : "Marcar como favorito")
      }
      aria-label={
        isFavorite ? "Quitar de favoritos" : "Marcar como favorito"
      }
      style={{
        background: "transparent",
        border: "none",
        cursor: saving ? "wait" : "pointer",
        padding: 2,
        lineHeight: 0,
        color: isFavorite ? "#fbbf24" : "rgba(148,163,184,0.55)",
        transition: "color 120ms ease",
      }}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill={isFavorite ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
      </svg>
    </button>
  );
}
