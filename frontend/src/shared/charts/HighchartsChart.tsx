import React, { useMemo } from 'react';
import Highcharts from './highchartsSetup';
import HighchartsReact from 'highcharts-react-official';
import type { ChartDataResponse } from '../../types/domain';

interface HighchartsChartProps {
  data: ChartDataResponse;
}

export const HighchartsChart: React.FC<HighchartsChartProps> = ({ data }) => {
  const options = useMemo<Highcharts.Options>(() => {
    const series = data.series.map((s) => ({
      type: 'column' as const,
      name: s.name,
      data: s.data,
      color: s.color,
      stacking: 'normal' as const,
      stack: s.stack,
    }));

    return {
      chart: {
        type: 'column',
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
            menuItems: ['downloadPNG', 'downloadJPEG', 'downloadSVG', 'separator', 'downloadCSV'],
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
