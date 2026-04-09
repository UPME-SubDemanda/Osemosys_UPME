import React, { useMemo } from "react";
import Highcharts from "./highchartsSetup";
import HighchartsReact from "highcharts-react-official";
import type { CompareChartFacetResponse, FacetData } from "../../types/domain";

interface CompareChartFacetProps {
  data: CompareChartFacetResponse;
}

function FacetChart({
  facet,
  yAxisLabel,
  showLegend,
}: {
  facet: FacetData;
  yAxisLabel: string;
  showLegend: boolean;
}) {
  const options = useMemo<Highcharts.Options>(() => {
    const series = facet.series.map((s) => ({
      type: "column" as const,
      name: s.name,
      data: s.data,
      color: s.color,
      stacking: "normal" as const,
      stack: s.stack,
    }));

    return {
      chart: {
        type: "column",
        height: 420,
        style: { fontFamily: "Verdana, sans-serif" },
        backgroundColor: "transparent",
      },
      title: {
        text: facet.scenario_name,
        style: { fontSize: "14px", fontWeight: "bold", color: "#f8fafc" },
      },
      xAxis: {
        categories: facet.categories,
        crosshair: { color: "#334155" },
        labels: { style: { color: "#94a3b8", fontSize: "13px" } },
        lineColor: "#334155",
        tickColor: "#334155",
      },
      yAxis: {
        min: 0,
        title: { text: yAxisLabel, style: { color: "#94a3b8", fontSize: "14px" } },
        labels: { style: { color: "#94a3b8", fontSize: "13px" } },
        gridLineColor: "#334155",
        stackLabels: {
          enabled: true,
          style: {
            fontWeight: "bold",
            color: "#cbd5e1",
            textOutline: "none",
            fontSize: "10px",
          },
          formatter: function (this: Highcharts.StackItemObject) {
            return Highcharts.numberFormat(this.total, 2, ".", ",");
          },
        },
      },
      tooltip: {
        headerFormat: "<b>{point.x}</b><br/>",
        pointFormat:
          "{series.name}: {point.y:,.2f} " +
          yAxisLabel +
          "<br/>Total: {point.stackTotal:,.2f} " +
          yAxisLabel,
        shared: true,
      },
      plotOptions: {
        column: { stacking: "normal", dataLabels: { enabled: false } },
      },
      series: series as Highcharts.SeriesOptionsType[],
      exporting: {
        enabled: true,
        sourceWidth: 1920,
        sourceHeight: 1080,
        scale: 1,
        fallbackToExportServer: false,
        chartOptions: {
          chart: { backgroundColor: "#FFFFFF" },
          title: { style: { color: "#1e293b", fontSize: "28px" } },
          xAxis: {
            labels: { style: { color: "#334155", fontSize: "20px" } },
            lineColor: "#cbd5e1",
            tickColor: "#cbd5e1",
          },
          yAxis: {
            labels: { style: { color: "#334155", fontSize: "20px" } },
            title: { style: { color: "#334155", fontSize: "22px" } },
            gridLineColor: "#e2e8f0",
            stackLabels: { style: { color: "#1e293b", fontSize: "16px" } },
          },
          legend: { itemStyle: { color: "#334155", fontSize: "20px" } },
        },
        buttons: {
          contextButton: {
            menuItems: ["downloadPNG", "downloadJPEG", "downloadSVG", "separator", "downloadCSV"],
          },
        },
      },
      credits: { enabled: false },
      legend: {
        enabled: showLegend,
        align: "center",
        verticalAlign: "bottom",
        layout: "horizontal",
        itemStyle: { color: "#94a3b8", fontWeight: "normal", fontSize: "13px" },
        itemHoverStyle: { color: "#f8fafc" },
      },
    };
  }, [facet, yAxisLabel, showLegend]);

  return (
    <HighchartsReact
      highcharts={Highcharts}
      options={options}
      containerProps={{ style: { width: "100%" } }}
    />
  );
}

export const CompareChartFacet: React.FC<CompareChartFacetProps> = ({ data }) => {
  const n = data.facets.length;

  return (
    <div className="w-full space-y-4">
      <h3
        className="text-base font-bold text-slate-100"
        style={{ fontSize: "16px" }}
      >
        {data.title}
      </h3>
      <div
        className={`grid gap-4 w-full ${
          n === 1
            ? "grid-cols-1"
            : `grid-cols-1 md:grid-cols-2 ${n >= 3 ? "lg:grid-cols-3" : ""}`
        }`}
      >
        {data.facets.map((facet, idx) => (
          <div
            key={facet.job_id}
            className="min-w-0 bg-[#1e293b]/30 rounded-lg p-2 border border-slate-700/30"
          >
            <FacetChart
              facet={facet}
              yAxisLabel={data.yAxisLabel}
              showLegend={idx === 0}
            />
          </div>
        ))}
      </div>
    </div>
  );
};
