/**
 * Celda compacta con la fecha relativa de un job ("Today at 1:11 AM",
 * "Apr 24 at 9:11 PM GMT-5") y su duración total ("2m 18s") en una segunda
 * línea con un ícono de cronómetro.
 *
 * Reemplaza las columnas separadas Encolado / Inicio / Fin de las tablas de
 * Simulación y Resultados. Si se pasa ``onClick``, la celda se vuelve un
 * botón clickeable para abrir los registros del job (logs).
 */
import type { ReactNode } from "react";

type Props = {
  /** ISO string — preferimos started_at; cae a queued_at si no inició aún. */
  startedAt?: string | null;
  /** ISO string — finished_at del job. */
  finishedAt?: string | null;
  /** ISO string — queued_at: usado como fallback si no hay started_at. */
  queuedAt?: string | null;
  /** Si está corriendo, calcula el tiempo desde started_at hasta ahora. */
  liveTickMs?: number | undefined;
  /** Click → suele abrir el modal de registros (logs). */
  onClick?: () => void;
  /** Tooltip para el botón. Default: "Ver registros". */
  title?: string;
};

/**
 * Formato corto de duración: ``2m 18s`` / ``5m 46s`` / ``45s`` / ``1h 12m``.
 * Devuelve null si no hay datos suficientes.
 */
export function formatDuration(seconds: number | null | undefined): string | null {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return null;
  const total = Math.floor(seconds);
  if (total < 60) return `${total}s`;
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return s > 0 ? `${h}h ${m}m` : `${h}h ${m}m`;
  if (s === 0) return `${m}m`;
  return `${m}m ${s}s`;
}

/**
 * Fecha relativa con formato: "Today at 1:11 AM" / "Yesterday at 3:30 PM" /
 * "Apr 24 at 9:11 PM GMT-5". Diseñado para ser compacto y legible.
 */
export function formatRelativeDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (!Number.isFinite(d.getTime())) return "—";

  const now = new Date();
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const isYesterday =
    d.getFullYear() === yesterday.getFullYear() &&
    d.getMonth() === yesterday.getMonth() &&
    d.getDate() === yesterday.getDate();

  const time = d.toLocaleTimeString("es-CO", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });

  if (sameDay) return `Hoy a las ${time}`;
  if (isYesterday) return `Ayer a las ${time}`;

  // Misma año: muestra "24 abr a las 9:11 PM"
  const sameYear = d.getFullYear() === now.getFullYear();
  const datePart = d.toLocaleDateString("es-CO", {
    day: "numeric",
    month: "short",
    ...(sameYear ? {} : { year: "numeric" }),
  });
  return `${datePart} a las ${time}`;
}

const calendarIcon = (
  <svg
    width={12}
    height={12}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
    <line x1="16" y1="2" x2="16" y2="6" />
    <line x1="8" y1="2" x2="8" y2="6" />
    <line x1="3" y1="10" x2="21" y2="10" />
  </svg>
);

const stopwatchIcon = (
  <svg
    width={12}
    height={12}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <circle cx="12" cy="13" r="8" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="2" x2="12" y2="4" />
    <line x1="8" y1="2" x2="16" y2="2" />
  </svg>
);

export function RunTimingCell({
  startedAt,
  finishedAt,
  queuedAt,
  liveTickMs,
  onClick,
  title,
}: Props) {
  // Para la fecha mostramos cuándo se ejecutó: started_at o, si no arrancó
  // aún, queued_at.
  const dateIso = startedAt ?? queuedAt ?? null;

  // Duración: finished_at - started_at. Si está corriendo (liveTickMs y
  // started_at sin finished_at), calcula desde started_at hasta ahora.
  let durationSeconds: number | null = null;
  if (startedAt) {
    const startMs = new Date(startedAt).getTime();
    if (Number.isFinite(startMs)) {
      const endMs = finishedAt ? new Date(finishedAt).getTime() : (liveTickMs ?? null);
      if (endMs != null && Number.isFinite(endMs)) {
        durationSeconds = (endMs - startMs) / 1000;
      }
    }
  }

  const dateLabel = formatRelativeDate(dateIso);
  const durationLabel = formatDuration(durationSeconds);

  const inner: ReactNode = (
    <div className="flex flex-col gap-0.5 text-left text-xs leading-tight">
      <span className="inline-flex items-center gap-1 text-slate-300">
        <span className="text-slate-500">{calendarIcon}</span>
        <span>{dateLabel}</span>
      </span>
      <span className="inline-flex items-center gap-1 text-slate-400">
        <span className="text-slate-500">{stopwatchIcon}</span>
        <span>{durationLabel ?? "—"}</span>
      </span>
    </div>
  );

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        title={title ?? "Ver registros del job"}
        className="block w-full rounded-md px-2 py-1 -mx-2 text-left transition-colors hover:bg-slate-800/60 hover:ring-1 hover:ring-slate-700"
      >
        {inner}
      </button>
    );
  }

  return inner;
}
