/**
 * Selector de corridas (SimulationRun) con vista enriquecida:
 * - ★ para favoritos
 * - Chips de etiquetas del escenario
 * - Agrupado en "Favoritos" y "Otros"
 * - Dropdown custom (<option> nativo no admite HTML → necesitamos popover)
 */
import { useEffect, useMemo, useRef, useState } from "react";

import { ScenarioTagChip } from "@/shared/components/ScenarioTagChip";
import type { ScenarioTag, SimulationRun } from "@/types/domain";

type Props = {
  value: number | null;
  onChange: (next: number | null) => void;
  jobs: SimulationRun[];
  loading?: boolean;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
};

function jobTitle(r: SimulationRun): string {
  return (
    r.display_name?.trim() ||
    r.scenario_name?.trim() ||
    r.input_name?.trim() ||
    `Job ${r.id}`
  );
}

function jobTags(r: SimulationRun): ScenarioTag[] {
  if (r.scenario_tags && r.scenario_tags.length > 0) return r.scenario_tags;
  if (r.scenario_tag) return [r.scenario_tag];
  return [];
}

function partitionJobs(jobs: SimulationRun[]): {
  favorites: SimulationRun[];
  others: SimulationRun[];
} {
  const sorted = [...jobs].sort(
    (a, b) => new Date(b.queued_at).getTime() - new Date(a.queued_at).getTime(),
  );
  const favorites: SimulationRun[] = [];
  const others: SimulationRun[] = [];
  for (const j of sorted) {
    (j.is_favorite ? favorites : others).push(j);
  }
  return { favorites, others };
}

export function JobSelect({
  value,
  onChange,
  jobs,
  loading = false,
  disabled = false,
  placeholder = "— Selecciona —",
  className = "",
}: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);
  const effectiveDisabled = disabled || loading;

  const selected = useMemo(
    () => jobs.find((j) => j.id === value) ?? null,
    [jobs, value],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return jobs;
    return jobs.filter((j) => {
      const title = jobTitle(j).toLowerCase();
      const tagText = jobTags(j)
        .map((t) => t.name)
        .join(" ")
        .toLowerCase();
      return (
        title.includes(q) ||
        tagText.includes(q) ||
        String(j.id).includes(q)
      );
    });
  }, [jobs, query]);

  const { favorites, others } = useMemo(
    () => partitionJobs(filtered),
    [filtered],
  );

  // Cerrar al hacer clic afuera
  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  // Cerrar con Escape
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div
      ref={rootRef}
      className={`relative ${className}`}
      style={{ minWidth: 260 }}
    >
      <button
        type="button"
        disabled={effectiveDisabled}
        onClick={() => setOpen((v) => !v)}
        className={[
          "w-full rounded-lg border border-slate-700 bg-slate-950/50 px-3 py-2 text-left text-sm text-slate-100",
          "flex items-center gap-2 min-h-[38px]",
          effectiveDisabled ? "opacity-60 cursor-not-allowed" : "cursor-pointer hover:border-slate-500",
        ].join(" ")}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        {selected ? (
          <SelectedRow job={selected} />
        ) : (
          <span className="text-slate-400">
            {loading ? "Cargando…" : placeholder}
          </span>
        )}
        <span className="ml-auto text-slate-400">{open ? "▴" : "▾"}</span>
      </button>

      {open ? (
        <div
          role="listbox"
          className="absolute z-50 mt-1 w-full max-h-[340px] overflow-auto rounded-lg border border-slate-700 bg-slate-950 shadow-xl"
          style={{ boxShadow: "0 12px 32px rgba(0,0,0,0.55)" }}
        >
          <div className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950 p-2">
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar por nombre, etiqueta o #id…"
              className="w-full rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-slate-500"
            />
          </div>

          <OptionRow
            empty
            label={loading ? "Cargando…" : "— Limpiar selección —"}
            onSelect={() => {
              onChange(null);
              setOpen(false);
            }}
            active={value == null}
          />

          {favorites.length > 0 ? (
            <>
              <GroupHeader label="★ Favoritos" />
              {favorites.map((j) => (
                <OptionRow
                  key={j.id}
                  job={j}
                  active={value === j.id}
                  onSelect={() => {
                    onChange(j.id);
                    setOpen(false);
                  }}
                />
              ))}
            </>
          ) : null}

          {others.length > 0 ? (
            <>
              {favorites.length > 0 ? <GroupHeader label="Otros" /> : null}
              {others.map((j) => (
                <OptionRow
                  key={j.id}
                  job={j}
                  active={value === j.id}
                  onSelect={() => {
                    onChange(j.id);
                    setOpen(false);
                  }}
                />
              ))}
            </>
          ) : null}

          {!loading && filtered.length === 0 ? (
            <div className="p-3 text-xs text-slate-500">Sin resultados.</div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function SelectedRow({ job }: { job: SimulationRun }) {
  const tags = jobTags(job);
  return (
    <span className="flex flex-1 items-center gap-2 min-w-0">
      {job.is_favorite ? (
        <span className="text-yellow-400" title="Favorito">
          ★
        </span>
      ) : null}
      <span className="truncate font-medium">{jobTitle(job)}</span>
      {tags.length > 0 ? (
        <span className="flex shrink-0 items-center gap-1">
          {tags.map((t) => (
            <ScenarioTagChip key={t.id} tag={t} size="sm" />
          ))}
        </span>
      ) : null}
      <span className="ml-1 shrink-0 font-mono text-[10px] text-slate-500">
        #{job.id}
      </span>
    </span>
  );
}

function GroupHeader({ label }: { label: string }) {
  return (
    <div className="sticky top-[38px] z-[1] border-b border-slate-800 bg-slate-900/80 px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
      {label}
    </div>
  );
}

function OptionRow({
  job,
  empty = false,
  label,
  active,
  onSelect,
}: {
  job?: SimulationRun;
  empty?: boolean;
  label?: string;
  active: boolean;
  onSelect: () => void;
}) {
  if (empty || !job) {
    return (
      <button
        type="button"
        role="option"
        aria-selected={active}
        onClick={onSelect}
        className={[
          "w-full px-3 py-2 text-left text-xs italic text-slate-400 hover:bg-slate-800/60",
          active ? "bg-slate-800/60" : "",
        ].join(" ")}
      >
        {label}
      </button>
    );
  }

  const tags = jobTags(job);
  return (
    <button
      type="button"
      role="option"
      aria-selected={active}
      onClick={onSelect}
      className={[
        "w-full px-3 py-2 text-left hover:bg-slate-800/60",
        active ? "bg-cyan-500/10 border-l-2 border-cyan-400" : "",
      ].join(" ")}
    >
      <div className="flex items-center gap-2 text-sm text-slate-100">
        <span className={job.is_favorite ? "text-yellow-400" : "text-slate-700"}>
          ★
        </span>
        <span className="truncate font-medium">{jobTitle(job)}</span>
        <span className="ml-auto shrink-0 font-mono text-[10px] text-slate-500">
          #{job.id}
        </span>
      </div>
      {tags.length > 0 ? (
        <div className="mt-1 flex flex-wrap gap-1 pl-6">
          {tags.map((t) => (
            <ScenarioTagChip key={t.id} tag={t} size="sm" />
          ))}
        </div>
      ) : null}
    </button>
  );
}
