import React, { useMemo } from 'react';
import Highcharts from './highchartsSetup';
import {
  EXPORTING_CONTEXT_BUTTON_DARK,
  onHighchartsExportError,
} from './chartExportingShared';
import HighchartsReact from 'highcharts-react-official';
import type { CompareChartResponse } from '../../types/domain';

interface CompareChartProps {
  data: CompareChartResponse;
  barOrientation?: 'vertical' | 'horizontal';
}

export const CompareChart: React.FC<CompareChartProps> = ({
  data,
  barOrientation = 'vertical',
}) => {
  const inverted = barOrientation === 'horizontal';
  const options = useMemo<Highcharts.Options>(() => {
    const numSubplots = data.subplots.length;

    const xAxis: Highcharts.XAxisOptions[] = [];
    const yAxis: Highcharts.YAxisOptions[] = [];
    const series: Highcharts.SeriesColumnOptions[] = [];

    const widthPerSubplot = 100 / (numSubplots || 1);

    data.subplots.forEach((subplot, idx) => {
      const leftStr = `${idx * widthPerSubplot}%`;
      const rightMargin = numSubplots > 1 && idx < numSubplots - 1 ? 2 : 0;
      const widthStr = `${widthPerSubplot - rightMargin}%`;

      xAxis.push({
        id: `x-${idx}`,
        categories: subplot.categories,
        title: {
          text: subplot.year.toString(),
          style: { color: '#94a3b8', fontWeight: 'bold' },
        },
        width: widthStr,
        left: leftStr,
        offset: 0,
        labels: { style: { color: '#94a3b8', fontSize: '13px' } },
        lineColor: '#334155',
        tickColor: '#334155',
      });

      yAxis.push({
        id: `y-${idx}`,
        title: {
          text: idx === 0 ? data.yAxisLabel : null,
          style: { color: '#94a3b8', fontSize: '14px' },
        },
        width: widthStr,
        left: leftStr,
        min: 0,
        gridLineColor: '#334155',
        labels: { style: { color: '#94a3b8', fontSize: '13px' } },
        stackLabels: {
          enabled: true,
          style: {
            fontWeight: 'bold',
            color: '#94a3b8',
            textOutline: 'none',
            fontSize: '10px',
          },
          // eslint-disable-next-line react-hooks/unsupported-syntax -- API de Highcharts (`this`)
          formatter: function (this: Highcharts.StackItemObject) {
            return Highcharts.numberFormat(this.total, 2, '.', ',');
          },
        },
      });

      subplot.series.forEach((s) => {
        series.push({
          type: 'column',
          name: s.name,
          data: s.data,
          color: s.color,
          xAxis: `x-${idx}`,
          yAxis: `y-${idx}`,
          stacking: 'normal',
          borderWidth: 0,
          showInLegend: idx === 0,
          tooltip: {
            valueDecimals: 2,
            valueSuffix: ` ${data.yAxisLabel}`,
          },
        });
      });
    });

    return {
      chart: {
        type: 'column',
        height: inverted ? 620 : 550,
        inverted,
        style: { fontFamily: 'Verdana, sans-serif' },
        backgroundColor: 'transparent',
        borderWidth: 0,
        plotBorderWidth: 0,
        plotShadow: false,
      },
      title: {
        text: data.title,
        style: { fontSize: '16px', fontWeight: 'bold', color: '#f8fafc' },
      },
      xAxis,
      yAxis,
      tooltip: { shared: false },
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
          legend: { itemStyle: { color: '#334155', fontSize: '20px' } },
        },
        buttons: {
          contextButton: {
            menuItems: ['downloadSVG'],
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
  }, [data, inverted]);

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
