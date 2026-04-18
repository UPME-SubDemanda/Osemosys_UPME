import React, { useMemo } from 'react';
import Highcharts from './highchartsSetup';
import {
  EXPORTING_CONTEXT_BUTTON_DARK,
  buildChartExportMenuItems,
  onHighchartsExportError,
} from './chartExportingShared';
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
  const options = useMemo<Highcharts.Options>(() => {
    const series = data.series.map((s) => ({
      type: 'column' as const,
      name: s.name,
      data: s.data,
      color: s.color,
      stacking: 'normal' as const,
      stack: s.stack,
      borderWidth: 0,
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
      tooltip: {
        headerFormat: '<b>{point.x}</b><br/>',
        pointFormat:
          '{series.name}: {point.y:,.2f} ' +
          data.yAxisLabel +
          '<br/>Total: {point.stackTotal:,.2f} ' +
          data.yAxisLabel,
        shared: true,
      },
      plotOptions: {
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
  }, [data, inverted, serverExport]);

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
