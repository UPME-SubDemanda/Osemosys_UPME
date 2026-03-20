import React, { useMemo } from 'react';
import Highcharts from './highchartsSetup';
import HighchartsReact from 'highcharts-react-official';
import type { CompareChartResponse } from '../../types/domain';

interface CompareChartProps {
  data: CompareChartResponse;
}

export const CompareChart: React.FC<CompareChartProps> = ({ data }) => {
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
        labels: { style: { color: '#94a3b8' } },
        lineColor: '#334155',
        tickColor: '#334155',
      });

      yAxis.push({
        id: `y-${idx}`,
        title: {
          text: idx === 0 ? data.yAxisLabel : null,
          style: { color: '#94a3b8' },
        },
        width: widthStr,
        left: leftStr,
        min: 0,
        gridLineColor: '#334155',
        labels: { style: { color: '#94a3b8' } },
        stackLabels: {
          enabled: true,
          style: {
            fontWeight: 'bold',
            color: '#cbd5e1',
            textOutline: 'none',
            fontSize: '10px',
          },
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
        height: 550,
        style: { fontFamily: 'inherit' },
        backgroundColor: 'transparent',
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
          dataLabels: { enabled: false },
        },
      },
      series: series as Highcharts.SeriesOptionsType[],
      exporting: {
        enabled: true,
        buttons: {
          contextButton: {
            menuItems: ['downloadPNG', 'downloadSVG', 'separator', 'downloadCSV'],
          },
        },
      },
      credits: { enabled: false },
      legend: {
        align: 'center',
        verticalAlign: 'bottom',
        layout: 'horizontal',
        itemStyle: { color: '#94a3b8', fontWeight: 'normal' },
        itemHoverStyle: { color: '#f8fafc' },
      },
    };
  }, [data]);

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
