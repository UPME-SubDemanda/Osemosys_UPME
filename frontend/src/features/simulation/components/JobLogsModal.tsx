/**
 * Modal mínimo para mostrar registros (logs) de un job de simulación.
 *
 * Reutilizable desde ResultsPage y otras vistas que sólo necesitan inspeccionar
 * la cronología sin la UI extendida (banners de infactibilidad, etapas en
 * vivo) que sí usa SimulationPage.
 */
import { useEffect, useState } from "react";
import { Modal } from "@/shared/components/Modal";
import { simulationApi } from "@/features/simulation/api/simulationApi";
import type { SimulationLog } from "@/types/domain";

type Props = {
  jobId: number | null;
  onClose: () => void;
};

export function JobLogsModal({ jobId, onClose }: Props) {
  const [logs, setLogs] = useState<SimulationLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (jobId == null) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    simulationApi
      .listLogs(jobId, 200, 1)
      .then((res) => {
        if (!cancelled) setLogs(res.data);
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "No se pudieron cargar los registros");
          setLogs([]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  return (
    <Modal
      open={jobId != null}
      title={jobId != null ? `Registros de la ejecución ${jobId}` : "Registros"}
      onClose={onClose}
    >
      {loading ? (
        <div style={{ display: "grid", gap: 8 }}>
          <div className="skeletonLine" />
          <div className="skeletonLine" />
          <div className="skeletonLine" />
        </div>
      ) : error ? (
        <div className="text-sm text-rose-300">{error}</div>
      ) : logs.length === 0 ? (
        <div className="text-sm text-slate-400">Sin registros disponibles para este job.</div>
      ) : (
        <ol
          className="grid gap-1.5 text-xs font-mono leading-relaxed"
          style={{ maxHeight: "60vh", overflowY: "auto" }}
        >
          {logs.map((l) => (
            <li
              key={l.id}
              className="grid grid-cols-[auto_auto_1fr] items-baseline gap-2 border-b border-slate-800/60 pb-1"
            >
              <span className="text-slate-500 tabular-nums">
                {new Date(l.created_at).toLocaleTimeString("es-CO")}
              </span>
              <span className="text-cyan-300">{l.stage ?? l.event_type}</span>
              <span className="text-slate-200 break-words">{l.message ?? "—"}</span>
            </li>
          ))}
        </ol>
      )}
    </Modal>
  );
}
