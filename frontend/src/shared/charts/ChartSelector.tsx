import React, { useEffect, useState } from 'react';
import { simulationApi } from '../../features/simulation/api/simulationApi';
import type { ChartCatalogItem } from '../../types/domain';

export interface ChartSelection {
  tipo: string;
  un: string;
  sub_filtro?: string;
  loc?: string;
  variable?: string;
}

interface ChartSelectorProps {
  value: ChartSelection;
  onChange: (selection: ChartSelection) => void;
}

const selectClass =
  'block w-full rounded-lg bg-[#0f172a] border border-slate-700 text-slate-200 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm px-3 py-2';

export const ChartSelector: React.FC<ChartSelectorProps> = ({ value, onChange }) => {
  const [catalog, setCatalog] = useState<ChartCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    simulationApi.getChartCatalog().then((data) => {
      setCatalog(data);
      if (data.length > 0 && !value.tipo && data[0]) {
        onChange({ ...value, tipo: data[0].id });
      }
      setLoading(false);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedConfig = catalog.find((c) => c.id === value.tipo);

  if (loading)
    return <div className="p-4 text-sm text-slate-500">Cargando tipos de grafica...</div>;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Tipo de Grafica */}
      <div>
        <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1.5">
          Tipo de Grafica
        </label>
        <select
          value={value.tipo}
          onChange={(e) =>
            onChange({ ...value, tipo: e.target.value, sub_filtro: '', loc: '', variable: '' })
          }
          className={selectClass}
        >
          {catalog.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
      </div>

      {/* Unidad */}
      <div>
        <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1.5">
          Unidad
        </label>
        <select
          value={value.un}
          onChange={(e) => onChange({ ...value, un: e.target.value })}
          className={selectClass}
        >
          <option value="PJ">PJ</option>
          <option value="GW">GW</option>
          <option value="MW">MW</option>
          <option value="TWh">TWh</option>
          <option value="Gpc">Gpc</option>
        </select>
      </div>

      {/* Variable de Capacidad */}
      {selectedConfig?.es_capacidad && (
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1.5">
            Variable de Capacidad
          </label>
          <select
            value={value.variable || ''}
            onChange={(e) => onChange({ ...value, variable: e.target.value })}
            className={selectClass}
          >
            <option value="">Capacidad Total</option>
            <option value="TotalCapacityAnnual">Capacidad Total</option>
            <option value="NewCapacity">Capacidad Nueva</option>
            <option value="AccumulatedNewCapacity">Capacidad Nueva Acumulada</option>
          </select>
        </div>
      )}

      {/* Sub-filtro */}
      {selectedConfig?.has_sub_filtro && (
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1.5">
            Sub-filtro
          </label>
          <select
            value={value.sub_filtro || ''}
            onChange={(e) => onChange({ ...value, sub_filtro: e.target.value })}
            className={selectClass}
          >
            <option value="">Todos</option>
            {selectedConfig.sub_filtros?.map((sf) => (
              <option key={sf} value={sf}>
                {sf}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Localizacion */}
      {selectedConfig?.has_loc && (
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1.5">
            Localizacion
          </label>
          <select
            value={value.loc || ''}
            onChange={(e) => onChange({ ...value, loc: e.target.value })}
            className={selectClass}
          >
            <option value="">Todos</option>
            <option value="URB">Urbano</option>
            <option value="RUR">Rural</option>
          </select>
        </div>
      )}
    </div>
  );
};
