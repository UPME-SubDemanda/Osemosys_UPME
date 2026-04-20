import { useEffect, useState } from "react";
import { Check, Pencil, X } from "lucide-react";
import { useToast } from "@/app/providers/useToast";
import { simulationApi } from "@/features/simulation/api/simulationApi";
import { Button } from "@/shared/components/Button";

type RunDisplayNameEditorProps = {
  jobId: number;
  value: string | null;
  onSaved: (jobId: number, next: string | null) => void;
  /** Fila de tabla: edición plegada con ícono. */
  compact?: boolean;
};

export function RunDisplayNameEditor({
  jobId,
  value,
  onSaved,
  compact = false,
}: RunDisplayNameEditorProps) {
  const { push } = useToast();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value ?? "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (compact) {
      if (!editing) setDraft(value ?? "");
    } else {
      setDraft(value ?? "");
    }
  }, [value, editing, compact]);

  const cancel = () => {
    setDraft(value ?? "");
    setEditing(false);
  };

  const save = async () => {
    const next = draft.trim() || null;
    setSaving(true);
    try {
      await simulationApi.patchDisplayName(jobId, next);
      onSaved(jobId, next);
      setEditing(false);
      push("Nombre del resultado actualizado.", "success");
    } catch (err) {
      console.error(err);
      push("No se pudo guardar el nombre.", "error");
    } finally {
      setSaving(false);
    }
  };

  const shown = (value ?? "").trim() || "—";

  if (!compact) {
    return (
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <input
          type="text"
          maxLength={255}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Nombre del resultado"
          className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-cyan-600 focus:outline-none focus:ring-1 focus:ring-cyan-600/40"
          disabled={saving}
        />
        <div className="flex shrink-0 gap-2">
          <Button
            type="button"
            onClick={() => void save()}
            disabled={saving}
            className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            <Check className="h-3.5 w-3.5" aria-hidden />
            Guardar
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={cancel}
            disabled={saving || draft.trim() === (value ?? "").trim()}
            className="inline-flex items-center gap-1 rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800 disabled:opacity-50"
          >
            <X className="h-3.5 w-3.5" aria-hidden />
            Deshacer
          </Button>
        </div>
      </div>
    );
  }

  if (!editing) {
    return (
      <div className="flex max-w-full items-center gap-2">
        <span className="min-w-0 truncate font-medium text-slate-200" title={shown === "—" ? undefined : shown}>
          {shown}
        </span>
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="inline-flex shrink-0 items-center rounded-md border border-slate-700 bg-slate-900/60 p-1.5 text-slate-400 hover:border-slate-600 hover:text-slate-200"
          title="Editar nombre del resultado"
          aria-label="Editar nombre del resultado"
        >
          <Pencil className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>
    );
  }

  return (
    <div className="flex min-w-[200px] max-w-full flex-col gap-2 sm:flex-row sm:items-center">
      <input
        type="text"
        maxLength={255}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        className="min-w-0 flex-1 rounded border border-slate-600 bg-slate-950 px-2 py-1.5 text-sm text-slate-100"
        disabled={saving}
        autoFocus
      />
      <div className="flex shrink-0 gap-1">
        <button
          type="button"
          onClick={() => void save()}
          disabled={saving}
          className="rounded border border-emerald-700/50 bg-emerald-950/50 p-1.5 text-emerald-300 hover:bg-emerald-900/40 disabled:opacity-50"
          title="Guardar"
          aria-label="Guardar nombre"
        >
          <Check className="h-3.5 w-3.5" aria-hidden />
        </button>
        <button
          type="button"
          onClick={cancel}
          disabled={saving}
          className="rounded border border-slate-700 bg-slate-900/60 p-1.5 text-slate-400 hover:bg-slate-800 disabled:opacity-50"
          title="Cancelar"
          aria-label="Cancelar edición"
        >
          <X className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>
    </div>
  );
}
