import React, { useEffect, useMemo, useRef, useState } from 'react';
import Highcharts from './highchartsSetup';
import {
  EXPORTING_CONTEXT_BUTTON_DARK,
  buildChartExportMenuItems,
  onHighchartsExportError,
} from './chartExportingShared';
import { buildStackedTooltipOptions } from './chartTooltips';
import {
  createLegendDblclickState,
  dispatchLegendClick,
} from './chartLegendInteractions';
import HighchartsReact from 'highcharts-react-official';
import type { ChartDataResponse } from '../../types/domain';
import type { ChartSelection } from './ChartSelector';

interface HighchartsChartProps {
  data: ChartDataResponse;
  /** Barras verticales (predeterminado) u horizontales (`inverted`). */
  barOrientation?: 'vertical' | 'horizontal';
  /** Si se indica, PNG/SVG/CSV se generan en el servidor (no dependen del navegador). */
  serverExport?: { jobId: number; selection: ChartSelection };
}

export const HighchartsChart: React.FC<HighchartsChartProps> = ({
  data,
  barOrientation = 'vertical',
  serverExport,
}) => {
  const inverted = barOrientation === 'horizontal';
  const legendDblclickStateRef = useRef(createLegendDblclickState());
  const [hiddenNames, setHiddenNames] = useState<Set<string>>(() => new Set());

  // Si cambia el dataset (nuevo tipo de chart), reseteamos la visibilidad.
  const dataSignature = useMemo(
    () => data.series.map((s) => s.name).join('|'),
    [data.series],
  );
  useEffect(() => {
    setHiddenNames(new Set());
    legendDblclickStateRef.current.isolatedName = null;
  }, [dataSignature]);

  const handleToggle = (name: string) => {
    setHiddenNames((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };
  const handleIsolate = (name: string) => {
    setHiddenNames(new Set(data.series.map((s) => s.name).filter((n) => n !== name)));
  };
  const handleRestoreAll = () => setHiddenNames(new Set());

  const options = useMemo<Highcharts.Options>(() => {
    const legendItemClick = function (this: Highcharts.Series): boolean {
      dispatchLegendClick(legendDblclickStateRef.current, this.name, {
        onToggle: handleToggle,
        onIsolate: handleIsolate,
        onRestoreAll: handleRestoreAll,
      });
      return false;
    };
    const series = data.series.map((s) => ({
      type: 'column' as const,
      name: s.name,
      data: s.data,
      color: s.color,
      stacking: 'normal' as const,
      stack: s.stack,
      borderWidth: 0,
      visible: !hiddenNames.has(s.name),
    }));

    return {
      chart: {
        type: 'column',
        height: inverted ? Math.min(640, 320 + data.categories.length * 16) : 500,
        inverted,
        style: { fontFamily: 'Verdana, sans-serif' },
        backgroundColor: 'transparent',
        borderWidth: 0,
        plotBorderWidth: 0,
        plotShadow: false,
      },
      title: {
        text: data.title,
        style: {
          fontSize: '16px',
          fontWeight: 'bold',
          color: '#f8fafc',
        },
      },
      xAxis: {
        categories: data.categories,
        crosshair: { color: '#334155' },
        labels: { style: { color: '#94a3b8', fontSize: '13px' } },
        lineColor: '#334155',
        tickColor: '#334155',
      },
      yAxis: {
        min: 0,
        title: {
          text: data.yAxisLabel,
          style: { color: '#94a3b8', fontSize: '14px' },
        },
        labels: { style: { color: '#94a3b8', fontSize: '13px' } },
        gridLineColor: '#334155',
        stackLabels: {
          enabled: true,
          style: {
            fontWeight: 'bold',
            color: '#94a3b8',
            textOutline: 'none',
            fontSize: '10px',
          },
          // Highcharts invoca el formatter con `this` como StackItemObject; no usar flecha.
          // eslint-disable-next-line react-hooks/unsupported-syntax -- API de Highcharts
          formatter: function (this: Highcharts.StackItemObject) {
            return Highcharts.numberFormat(this.total, 2, '.', ',');
          },
        },
      },
      tooltip: buildStackedTooltipOptions({ unitLabel: data.yAxisLabel }),
      plotOptions: {
        series: {
          events: { legendItemClick },
        },
        column: {
          stacking: 'normal',
          borderWidth: 0,
          dataLabels: { enabled: false },
        },
      },
      series: series as Highcharts.SeriesOptionsType[],
      exporting: {
        enabled: true,
        sourceWidth: 1920,
        sourceHeight: 1080,
        scale: 1,
        fallbackToExportServer: false,
        error: onHighchartsExportError,
        chartOptions: {
          chart: { backgroundColor: '#FFFFFF' },
          title: { style: { color: '#1e293b', fontSize: '28px' } },
          xAxis: {
            labels: { style: { color: '#334155', fontSize: '20px' } },
            lineColor: '#cbd5e1',
            tickColor: '#cbd5e1',
          },
          yAxis: {
            labels: { style: { color: '#334155', fontSize: '20px' } },
            title: { style: { color: '#334155', fontSize: '22px' } },
            gridLineColor: '#e2e8f0',
            stackLabels: { style: { color: '#1e293b', fontSize: '16px' } },
          },
          legend: { itemStyle: { color: '#334155', fontSize: '20px' } },
        },
        buttons: {
          contextButton: {
            // Highcharts admite objetos { text, onclick }; los tipos suelen declarar solo string[].
            menuItems: buildChartExportMenuItems(serverExport) as string[],
            ...EXPORTING_CONTEXT_BUTTON_DARK,
          },
        },
      },
      credits: { enabled: false },
      legend: {
        align: 'center',
        verticalAlign: 'bottom',
        layout: 'horizontal',
        itemStyle: { color: '#94a3b8', fontWeight: 'normal', fontSize: '13px' },
        itemHoverStyle: { color: '#f8fafc' },
      },
    };
    // `handleToggle/handleIsolate/handleRestoreAll` viven en closures estables
    // por componente; sus dependencias reales son `data` (para `handleIsolate`) y
    // `hiddenNames` (para `options.series[i].visible`).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, inverted, serverExport, hiddenNames]);

  return (
    <div style={{ width: '100%' }}>
      <HighchartsReact
        highcharts={Highcharts}
        options={options}
        containerProps={{ style: { width: '100%' } }}
      />
    </div>
  );
};
