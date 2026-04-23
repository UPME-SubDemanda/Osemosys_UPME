import React, { useEffect, useState } from 'react';
import { simulationApi } from '../../features/simulation/api/simulationApi';
import { ScenarioTagChip } from '@/shared/components/ScenarioTagChip';
import type { SimulationRun } from '../../types/domain';

export type CompareViewMode = 'facet' | 'by-year';

interface ScenarioComparerProps {
  currentRunId: number;
  selectedJobIds: number[];
  selectedYears: number[];
  compareViewMode: CompareViewMode;
  enabled: boolean;
  onToggle: () => void;
  onChange: (selection: { jobIds: number[]; yearsToPlot: number[]; compareViewMode?: CompareViewMode }) => void;
}

const AVAILABLE_YEARS = [2022, 2024, 2025, 2030, 2035, 2040, 2045, 2050, 2054];

export const ScenarioComparer: React.FC<ScenarioComparerProps> = ({
  currentRunId,
  selectedJobIds,
  selectedYears,
  compareViewMode,
  enabled,
  onToggle,
  onChange,
}) => {
  const [runs, setRuns] = useState<SimulationRun[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    simulationApi
      .listRuns({ scope: 'global', status_filter: 'SUCCEEDED', cantidad: 50 })
      .then((data) => {
        // Solo escenarios con resultados utilizables (excluye infactibles).
        setRuns((data.data || []).filter((r) => !r.is_infeasible_result));
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!selectedJobIds.includes(currentRunId)) {
      onChange({ jobIds: [currentRunId, ...selectedJobIds], yearsToPlot: selectedYears, compareViewMode });
    }
  }, [currentRunId, selectedJobIds, selectedYears, compareViewMode, onChange]);

  if (loading) return null;

  const handleJobToggle = (jobId: number) => {
    if (jobId === currentRunId) return;

    let newJobIds = [...selectedJobIds];
    if (newJobIds.includes(jobId)) {
      newJobIds = newJobIds.filter((id) => id !== jobId);
    } else {
      if (newJobIds.length >= 10) {
        alert('Maximo 10 escenarios para comparar.');
        return;
      }
      newJobIds.push(jobId);
    }
    onChange({ jobIds: newJobIds, yearsToPlot: selectedYears, compareViewMode });
  };

  const handleViewModeChange = (mode: CompareViewMode) => {
    onChange({ jobIds: selectedJobIds, yearsToPlot: selectedYears, compareViewMode: mode });
  };

  const handleYearToggle = (year: number) => {
    let newYears = [...selectedYears];
    if (newYears.includes(year)) {
      if (newYears.length <= 1) return;
      newYears = newYears.filter((y) => y !== year);
    } else {
      newYears.push(year);
      newYears.sort((a, b) => a - b);
    }
    onChange({ jobIds: selectedJobIds, yearsToPlot: newYears, compareViewMode });
  };

  return (
    <div className="flex flex-col md:flex-row gap-4">
      {/* Scenario selection */}
      <div className="bg-[#1e293b] p-4 rounded-xl border border-slate-700/50 flex-1">
        <div className="flex items-center mb-3 text-slate-300">
          <button
            type="button"
            role="switch"
            aria-checked={enabled}
            onClick={onToggle}
            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-[#1e293b] mr-3 ${
              enabled ? 'bg-blue-600' : 'bg-slate-600'
            }`}
          >
            <span
              className={`inline-block h-3 w-3 rounded-full bg-white transition-transform ${
                enabled ? 'translate-x-5' : 'translate-x-1'
              }`}
            />
          </button>
          <span className="text-sm font-bold">
            Comparar Escenarios
            {enabled && (
              <span className="ml-2 font-normal text-slate-500">
                ({selectedJobIds.length} seleccionados)
              </span>
            )}
          </span>
        </div>

        {enabled && (
          <>
            <div className="flex items-center gap-4 mb-3">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Vista:</span>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="compareView"
                  checked={compareViewMode === 'facet'}
                  onChange={() => handleViewModeChange('facet')}
                  className="w-4 h-4 border-2 border-slate-500 text-blue-500 focus:ring-blue-500 focus:ring-offset-0 focus:ring-offset-[#1e293b] bg-[#0f172a]"
                />
                <span className="text-sm text-slate-300">Escenarios completos</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="compareView"
                  checked={compareViewMode === 'by-year'}
                  onChange={() => handleViewModeChange('by-year')}
                  className="w-4 h-4 border-2 border-slate-500 text-blue-500 focus:ring-blue-500 focus:ring-offset-0 focus:ring-offset-[#1e293b] bg-[#0f172a]"
                />
                <span className="text-sm text-slate-300">Por años seleccionados</span>
              </label>
            </div>
            <div className="overflow-y-auto max-h-[180px] pr-1 space-y-1 custom-scrollbar">
            {runs.map((run) => (
              <label
                key={run.id}
                className={`flex items-center px-3 py-2 rounded-lg cursor-pointer transition-colors ${
                  selectedJobIds.includes(run.id)
                    ? 'bg-slate-800/80 border border-slate-600'
                    : 'hover:bg-slate-800/50 border border-transparent'
                }`}
              >
                <div className="relative flex items-center justify-center w-4 h-4 mr-3">
                  <input
                    type="checkbox"
                    checked={selectedJobIds.includes(run.id)}
                    disabled={run.id === currentRunId}
                    onChange={() => handleJobToggle(run.id)}
                    className="peer appearance-none w-4 h-4 border-2 border-slate-500 rounded bg-[#0f172a] checked:bg-blue-500 checked:border-blue-500 focus:outline-none transition-all cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
                  />
                  <svg
                    className="absolute pointer-events-none opacity-0 peer-checked:opacity-100 text-white"
                    width="10"
                    height="10"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <span
                  className={`flex flex-wrap items-center gap-2 text-sm select-none ${selectedJobIds.includes(run.id) ? 'text-slate-200 font-medium' : 'text-slate-400'}`}
                >
                  <span>
                    {run.display_name?.trim() || run.scenario_name || `Job #${run.id}`}
                    {run.id === currentRunId && (
                      <span className="ml-2 text-[10px] text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded">
                        (Actual)
                      </span>
                    )}
                  </span>
                  {run.scenario_tag ? <ScenarioTagChip tag={run.scenario_tag} /> : null}
                </span>
              </label>
            ))}
          </div>
          </>
        )}
      </div>

      {/* Year selection - solo visible en modo by-year */}
      {enabled && compareViewMode === 'by-year' && (
      <div className="bg-[#1e293b] p-4 rounded-xl border border-slate-700/50">
        <h3 className="text-sm font-bold text-slate-300 mb-3">
          Años a graficar
        </h3>

        <div className="flex flex-wrap gap-2 content-start">
          {AVAILABLE_YEARS.map((year) => {
            const isSelected = selectedYears.includes(year);
            return (
              <label
                key={year}
                className={`flex items-center justify-center px-3 py-1.5 rounded-full text-sm font-medium cursor-pointer transition-colors border select-none ${
                  isSelected
                    ? 'bg-blue-600/20 text-blue-400 border-blue-500/50'
                    : 'bg-[#0f172a] text-slate-400 border-slate-700 hover:border-slate-500'
                }`}
              >
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => handleYearToggle(year)}
                  className="hidden"
                />
                {year}
              </label>
            );
          })}
        </div>
      </div>
      )}
    </div>
  );
};
