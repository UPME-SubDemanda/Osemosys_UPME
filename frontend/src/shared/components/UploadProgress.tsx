/**
 * Barra de progreso para subida y procesamiento de archivos Excel.
 * Muestra fases: idle, uploading, processing, done, error.
 * Usa estimación por tamaño de archivo y tiempo transcurrido.
 */
import { useEffect, useRef, useState } from "react";

export type UploadPhase = "idle" | "uploading" | "processing" | "done" | "error";

type Props = {
  phase: UploadPhase;
  uploadPercent: number;
  fileSizeBytes: number;
  startedAt: number | null;
  /** Si `phase === "done"`, sustituye el texto «Completado». */
  doneLabel?: string;
  /** Tono de la barra al terminar: «conflicts» (ámbar) o éxito (verde). */
  doneVariant?: "success" | "conflicts";
};

function formatTime(seconds: number): string {
  if (seconds < 60) return `${Math.ceil(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.ceil(seconds % 60);
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

export function UploadProgress({
  phase,
  uploadPercent,
  fileSizeBytes,
  startedAt,
  doneLabel,
  doneVariant = "success",
}: Props) {
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (phase === "uploading" || phase === "processing") {
      timerRef.current = setInterval(() => {
        if (startedAt) setElapsed(Date.now() - startedAt);
      }, 500);
    } else if (phase === "done" || phase === "error") {
      queueMicrotask(() => {
        if (startedAt) setElapsed(Date.now() - startedAt);
      });
    } else {
      queueMicrotask(() => setElapsed(0));
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [phase, startedAt]);

  if (phase === "idle") return null;

  const elapsedSec = elapsed / 1000;

  let displayPercent = 0;
  let label = "";
  let estimateText = "";
  let hint = "";

  if (phase === "uploading") {
    displayPercent = Math.min(uploadPercent * 0.15, 15);
    label = `Subiendo archivo... ${Math.round(uploadPercent)}%`;
  } else if (phase === "processing") {
    const slow = 1 - 1 / (1 + elapsedSec / 300);
    displayPercent = 15 + slow * 70;
    label = "Procesando datos en el servidor...";
    estimateText = `${formatTime(elapsedSec)} transcurridos`;
    const fileSizeMB = fileSizeBytes / (1024 * 1024);
    hint = `Leyendo, validando e insertando datos (${fileSizeMB.toFixed(1)} MB). No cierres esta ventana.`;
  } else if (phase === "done") {
    displayPercent = 100;
    label = doneLabel?.trim() ? doneLabel.trim() : "Completado";
    estimateText = elapsedSec > 1 ? `Terminado en ${formatTime(elapsedSec)}` : "";
  } else if (phase === "error") {
    label = "Error en el proceso";
    estimateText = elapsedSec > 1 ? `Falló después de ${formatTime(elapsedSec)}` : "";
  }

  const barColor =
    phase === "done"
      ? doneVariant === "conflicts"
        ? "rgba(245, 158, 11, 0.9)"
        : "rgba(34, 197, 94, 0.85)"
      : phase === "error"
        ? "rgba(239, 68, 68, 0.85)"
        : "linear-gradient(90deg, rgba(31, 94, 164, 0.9), rgba(20, 184, 122, 0.85))";

  const isPulsing = phase === "processing";

  return (
    <div
      style={{
        display: "grid",
        gap: 8,
        padding: 14,
        borderRadius: 12,
        border: `1px solid ${
          phase === "error"
            ? "rgba(239,68,68,0.3)"
            : phase === "done" && doneVariant === "conflicts"
              ? "rgba(245,158,11,0.35)"
              : "rgba(255,255,255,0.1)"
        }`,
        background:
          phase === "error"
            ? "rgba(239,68,68,0.06)"
            : phase === "done" && doneVariant === "conflicts"
              ? "rgba(245,158,11,0.08)"
              : "rgba(255,255,255,0.03)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 14, fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>
          {isPulsing ? (
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: "rgba(20, 184, 122, 0.9)",
                animation: "pulse-dot 1.5s ease-in-out infinite",
                flexShrink: 0,
              }}
            />
          ) : null}
          {label}
        </span>
        {estimateText ? (
          <span style={{ fontSize: 13, opacity: 0.7, whiteSpace: "nowrap" }}>{estimateText}</span>
        ) : null}
      </div>

      <div
        style={{
          height: 8,
          borderRadius: 999,
          background: "rgba(255,255,255,0.08)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${Math.max(displayPercent, phase === "error" ? 100 : 2)}%`,
            borderRadius: 999,
            background: barColor,
            transition: "width 0.8s ease",
          }}
        />
      </div>

      {hint ? <small style={{ opacity: 0.6, fontSize: 12 }}>{hint}</small> : null}

      <style>{`
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.4; transform: scale(0.7); }
        }
      `}</style>
    </div>
  );
}
