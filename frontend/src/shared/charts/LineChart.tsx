import React, { useEffect, useMemo, useRef, useState } from 'react';
import Highcharts from './highchartsSetup';
import {
  EXPORTING_CONTEXT_BUTTON_DARK,
  buildChartExportMenuItems,
  onHighchartsExportError,
} from './chartExportingShared';
import { buildLineTooltipOptions } from './chartTooltips';
import {
  createLegendDblclickState,
  dispatchLegendClick,
} from './chartLegendInteractions';
import HighchartsReact from 'highcharts-react-official';
import type { ChartDataResponse } from '../../types/domain';
import type { ChartSelection } from './ChartSelector';

interface LineChartProps {
  data: ChartDataResponse;
  serverExport?: { jobId: number; selection: ChartSelection };
}

export const LineChart: React.FC<LineChartProps> = ({ data, serverExport }) => {
  const legendDblclickStateRef = useRef(createLegendDblclickState());
  const [hiddenNames, setHiddenNames] = useState<Set<string>>(() => new Set());

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
      type: 'line' as const,
      name: s.name,
      data: s.data,
      color: s.color,
      marker: { enabled: true, radius: 3 },
      visible: !hiddenNames.has(s.name),
    }));

    return {
      chart: {
        type: 'line',
        height: 500,
        style: { fontFamily: 'Verdana, sans-serif' },
        backgroundColor: 'transparent',
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
      },
      tooltip: buildLineTooltipOptions({ unitLabel: data.yAxisLabel }),
      plotOptions: {
        series: {
          events: { legendItemClick },
        },
        line: {
          dataLabels: { enabled: false },
          marker: { enabled: true, radius: 3 },
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
            labels: { style: { color: '#334155', fontSize: '22px' } },
            title: { style: { color: '#334155', fontSize: '24px' } },
            gridLineColor: '#e2e8f0',
          },
          legend: { itemStyle: { color: '#334155', fontSize: '24px' } },
        },
        buttons: {
          contextButton: {
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, serverExport, hiddenNames]);

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
