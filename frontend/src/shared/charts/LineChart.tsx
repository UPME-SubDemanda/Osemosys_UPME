import React, { useMemo } from 'react';
import Highcharts from './highchartsSetup';
import HighchartsReact from 'highcharts-react-official';
import type { ChartDataResponse } from '../../types/domain';

interface LineChartProps {
  data: ChartDataResponse;
}

export const LineChart: React.FC<LineChartProps> = ({ data }) => {
  const options = useMemo<Highcharts.Options>(() => {
    const series = data.series.map((s) => ({
      type: 'line' as const,
      name: s.name,
      data: s.data,
      color: s.color,
      marker: { enabled: true, radius: 3 },
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
      tooltip: {
        shared: true,
        crosshairs: true,
        headerFormat: '<b>{point.key}</b><br/>',
        pointFormat:
          '<span style="color:{series.color}">●</span> {series.name}: <b>{point.y:,.2f}</b> ' +
          data.yAxisLabel +
          '<br/>',
      },
      plotOptions: {
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
