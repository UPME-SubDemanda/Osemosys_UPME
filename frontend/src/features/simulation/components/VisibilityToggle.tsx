/**
 * Chip interactivo que muestra y edita la visibilidad de un resultado.
 *
 *   - Público (todos ven) → clic alterna a privado (si el usuario es dueño).
 *   - Privado (solo dueño) → clic alterna a público.
 *
 * Si el usuario actual no es el dueño, solo muestra el chip (no editable).
 */
import { useState } from "react";
import { simulationApi } from "@/features/simulation/api/simulationApi";

type Props = {
  jobId: number;
  isPublic: boolean;
  canEdit: boolean;
  onChanged?: (next: boolean) => void;
  compact?: boolean;
};

export function VisibilityToggle({
  jobId,
  isPublic,
  canEdit,
  onChanged,
  compact = false,
}: Props) {
  const [saving, setSaving] = useState(false);
  const base =
    "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-semibold uppercase tracking-wider";
  const sizeCls = compact
    ? "text-[10px]"
    : "text-xs";
  const publicCls = isPublic
    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
    : "border-amber-500/30 bg-amber-500/10 text-amber-300";
  const className = `${base} ${sizeCls} ${publicCls}`;

  const handleClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    if (!canEdit || saving) return;
    const next = !isPublic;
    setSaving(true);
    try {
      await simulationApi.patchVisibility(jobId, next);
      onChanged?.(next);
    } catch (err) {
      console.error("Error changing visibility", err);
    } finally {
      setSaving(false);
    }
  };

  const label = isPublic ? "Público" : "Privado";
  const icon = isPublic ? (
    <svg width={11} height={11} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <circle cx="12" cy="12" r="10" />
      <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  ) : (
    <svg width={11} height={11} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <rect x="3" y="11" width="18" height="11" rx="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );

  if (!canEdit) {
    return (
      <span className={className} title={`Visibilidad: ${label}`}>
        {icon}
        {label}
      </span>
    );
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={saving}
      title={
        saving
          ? "Guardando…"
          : isPublic
            ? "Cambiar a privado (solo yo)"
            : "Cambiar a público (todos los usuarios)"
      }
      className={`${className} cursor-pointer hover:brightness-125 disabled:opacity-50`}
    >
      {icon}
      {label}
    </button>
  );
}
