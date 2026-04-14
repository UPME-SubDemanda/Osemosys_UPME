import React, { useEffect, useMemo, useRef, useState } from "react";
import Highcharts from "./highchartsSetup";
import { onHighchartsExportError } from "./chartExportingShared";
import HighchartsReact from "highcharts-react-official";
import type { CompareChartFacetResponse, FacetData } from "../../types/domain";
import type {
  ChartBarOrientation,
  ChartFacetLegendMode,
  ChartFacetPlacement,
} from "./chartLayoutPreferences";

interface CompareChartFacetProps {
  data: CompareChartFacetResponse;
  barOrientation?: ChartBarOrientation;
  facetPlacement?: ChartFacetPlacement;
  /** Predeterminado: leyenda compartida (panel React). */
  legendMode?: ChartFacetLegendMode;
}

function FacetChart({
  facet,
  yAxisLabel,
  sharedYAxisMax,
  syncGroup,
  hiddenSeriesNames,
  onLegendToggle,
  inverted,
  chartHeight,
  showHighchartsLegend,
  hoveredSeriesName = null,
}: {
  facet: FacetData;
  yAxisLabel: string;
  sharedYAxisMax: number;
  syncGroup: string;
  hiddenSeriesNames: Set<string>;
  onLegendToggle: (seriesName: string) => void;
  inverted: boolean;
  chartHeight: number;
  showHighchartsLegend: boolean;
  /** Resaltado sincronizado con leyenda compartida (hover). */
  hoveredSeriesName?: string | null;
}) {
  const chartRef = useRef<Highcharts.Chart | null>(null);
  const [chartGeneration, setChartGeneration] = useState(0);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart?.series?.length) return;
    chart.series.forEach((s) => {
      if (!s.visible) {
        s.setState("");
        return;
      }
      if (!hoveredSeriesName) {
        s.setState("");
        return;
      }
      if (s.name === hoveredSeriesName) {
        s.setState("hover");
      } else {
        s.setState("inactive");
      }
    });
  }, [hoveredSeriesName, facet, hiddenSeriesNames, chartGeneration]);

  const options = useMemo<Highcharts.Options>(() => {
    const series = facet.series.map((s) => ({
      type: "column" as const,
      name: s.name,
      data: s.data,
      color: s.color,
      stacking: "normal" as const,
      stack: s.stack,
      visible: !hiddenSeriesNames.has(s.name),
    }));

    return {
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
        events: {
          afterSetExtremes(event) {
            const evt = event as Highcharts.AxisSetExtremesEventObject & {
              trigger?: string;
            };
            if (evt.trigger === "sync-facet-x") return;
            const sourceChart = this.chart as Highcharts.Chart & {
              __facetSyncGroup?: string;
            };
            Highcharts.charts.forEach((chartCandidate) => {
              const targetChart = chartCandidate as
                | (Highcharts.Chart & { __facetSyncGroup?: string })
                | undefined;
              if (!targetChart || targetChart === sourceChart) return;
              if (targetChart.__facetSyncGroup !== syncGroup) return;
              const axis = targetChart.xAxis?.[0];
              if (!axis) return;
              axis.setExtremes(evt.min, evt.max, true, false, {
                trigger: "sync-facet-x",
              } as Highcharts.AxisSetExtremesEventObject);
            });
          },
        },
      },
      yAxis: {
        min: 0,
        max: sharedYAxisMax > 0 ? sharedYAxisMax : null,
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
          // eslint-disable-next-line react-hooks/unsupported-syntax -- API de Highcharts (`this`)
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
        series: {
          states: {
            inactive: {
              enabled: true,
              opacity: 0.35,
            },
            hover: {
              enabled: true,
              brightness: 0.12,
            },
          },
          events: showHighchartsLegend
            ? {
                // Sincroniza visibilidad de series entre todas las facetas del mismo grupo.
                legendItemClick: function (this: Highcharts.Series) {
                  onLegendToggle(this.name);
                  return false;
                },
              }
            : {},
        },
        column: { stacking: "normal", dataLabels: { enabled: false } },
      },
      series: series as Highcharts.SeriesOptionsType[],
      chart: {
        type: "column",
        height: chartHeight,
        inverted,
        style: { fontFamily: "Verdana, sans-serif" },
        backgroundColor: "transparent",
        events: {
          load() {
            (this as Highcharts.Chart & { __facetSyncGroup?: string }).__facetSyncGroup =
              syncGroup;
          },
        },
      },
      exporting: {
        enabled: true,
        sourceWidth: 1920,
        sourceHeight: 1080,
        scale: 1,
        fallbackToExportServer: false,
        error: onHighchartsExportError,
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
            menuItems: ["downloadSVG"],
          },
        },
      },
      credits: { enabled: false },
      legend: {
        enabled: showHighchartsLegend,
        align: "center",
        verticalAlign: "bottom",
        layout: "horizontal",
        itemStyle: { color: "#94a3b8", fontWeight: "normal", fontSize: "13px" },
        itemHoverStyle: { color: "#f8fafc" },
      },
    };
  }, [
    facet,
    yAxisLabel,
    sharedYAxisMax,
    syncGroup,
    hiddenSeriesNames,
    onLegendToggle,
    inverted,
    chartHeight,
    showHighchartsLegend,
  ]);

  return (
    <HighchartsReact
      highcharts={Highcharts}
      options={options}
      callback={(chart: Highcharts.Chart) => {
        chartRef.current = chart;
        setChartGeneration((g) => g + 1);
      }}
      containerProps={{ style: { width: "100%" } }}
    />
  );
}

function buildSharedLegendItems(facets: FacetData[]): { name: string; color: string }[] {
  const byName = new Map<string, string>();
  for (const facet of facets) {
    for (const s of facet.series) {
      if (!byName.has(s.name)) byName.set(s.name, s.color);
    }
  }
  return Array.from(byName.entries()).map(([name, color]) => ({ name, color }));
}

export const CompareChartFacet: React.FC<CompareChartFacetProps> = ({
  data,
  barOrientation = "vertical",
  facetPlacement = "inline",
  legendMode = "shared",
}) => {
  const inverted = barOrientation === "horizontal";
  const n = data.facets.length;
  const seriesStateSignature = useMemo(
    () => `${data.title}|${data.facets.map((f) => f.job_id).join(",")}`,
    [data.title, data.facets],
  );
  const [legendState, setLegendState] = useState<{
    signature: string;
    hiddenSeriesNames: Set<string>;
  }>({
    signature: seriesStateSignature,
    hiddenSeriesNames: new Set(),
  });
  const hiddenSeriesNames =
    legendState.signature === seriesStateSignature
      ? legendState.hiddenSeriesNames
      : new Set<string>();

  const [legendHover, setLegendHover] = useState<{
    dataSig: string;
    seriesName: string | null;
  } | null>(null);

  const effectiveLegendHover =
    legendHover && legendHover.dataSig === seriesStateSignature
      ? legendHover.seriesName
      : null;

  const handleLegendToggle = (seriesName: string) => {
    setLegendHover({ dataSig: seriesStateSignature, seriesName: null });
    setLegendState((prev) => {
      const baseHidden =
        prev.signature === seriesStateSignature ? prev.hiddenSeriesNames : new Set<string>();
      const next = new Set(baseHidden);
      if (next.has(seriesName)) next.delete(seriesName);
      else next.add(seriesName);
      return {
        signature: seriesStateSignature,
        hiddenSeriesNames: next,
      };
    });
  };

  const facetChartHeight = useMemo(() => {
    const catLen = Math.max(
      ...data.facets.map((f) => f.categories.length),
      1,
    );
    if (inverted) {
      return Math.min(680, 260 + catLen * 16);
    }
    return 420;
  }, [data.facets, inverted]);

  const sharedLegendItems = useMemo(
    () => buildSharedLegendItems(data.facets),
    [data.facets],
  );

  const sharedYAxisMax = useMemo(() => {
    let globalMax = 0;
    data.facets.forEach((facet) => {
      const categoryCount = facet.categories.length;
      for (let i = 0; i < categoryCount; i += 1) {
        const stackTotal = facet.series.reduce((acc, serie) => {
          const point = serie.data[i];
          return acc + (typeof point === "number" ? point : 0);
        }, 0);
        if (stackTotal > globalMax) globalMax = stackTotal;
      }
    });
    return globalMax;
  }, [data.facets]);

  const isStacked = facetPlacement === "stacked";
  const useSharedLegendPanel = legendMode === "shared" && sharedLegendItems.length > 0;

  return (
    <div className="w-full space-y-4">
      <h3
        className="text-base font-bold text-slate-100"
        style={{ fontSize: "16px" }}
      >
        {data.title}
      </h3>
      {useSharedLegendPanel ? (
        <div
          className="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-3"
          role="group"
          aria-label="Leyenda de series (compartida)"
        >
          <p className="m-0 mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">
            Leyenda (todas las gráficas)
          </p>
          <div className="flex flex-wrap gap-2">
            {sharedLegendItems.map(({ name, color }) => {
              const hidden = hiddenSeriesNames.has(name);
              const isLegendHover = !hidden && effectiveLegendHover === name;
              return (
                <button
                  key={name}
                  type="button"
                  onClick={() => handleLegendToggle(name)}
                  onMouseEnter={() => {
                    if (!hidden) {
                      setLegendHover({ dataSig: seriesStateSignature, seriesName: name });
                    }
                  }}
                  onMouseLeave={() =>
                    setLegendHover({ dataSig: seriesStateSignature, seriesName: null })
                  }
                  onFocus={() => {
                    if (!hidden) {
                      setLegendHover({ dataSig: seriesStateSignature, seriesName: name });
                    }
                  }}
                  onBlur={() =>
                    setLegendHover({ dataSig: seriesStateSignature, seriesName: null })
                  }
                  title={hidden ? "Mostrar serie" : "Ocultar serie"}
                  className={[
                    "inline-flex max-w-full items-center gap-2 rounded-full border px-2.5 py-1 text-left text-xs font-medium transition-colors",
                    hidden
                      ? "border-slate-700 bg-slate-900/60 text-slate-500 line-through opacity-70"
                      : [
                          "border-slate-600 bg-slate-900/40 text-slate-200 hover:border-slate-500 hover:bg-slate-800/60",
                          isLegendHover
                            ? "ring-2 ring-cyan-400/50 border-cyan-500/35 bg-slate-800/80 z-10"
                            : "",
                        ].join(" "),
                  ].join(" ")}
                >
                  <span
                    className="h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: hidden ? "#475569" : color }}
                    aria-hidden
                  />
                  <span className="min-w-0 truncate">{name}</span>
                </button>
              );
            })}
          </div>
        </div>
      ) : null}
      <div
        className={
          isStacked
            ? "w-full pb-2"
            : "w-full overflow-x-auto pb-2"
        }
      >
        <div
          className={
            isStacked
              ? "flex flex-col gap-4 w-full"
              : "flex flex-nowrap items-stretch gap-4 w-full min-w-full"
          }
          style={
            isStacked
              ? undefined
              : {
                  width: n === 1 ? "100%" : "max-content",
                  minWidth: n === 1 ? "100%" : "100%",
                }
          }
        >
          {data.facets.map((facet, idx) => (
            <div
              key={facet.job_id}
              className="bg-[#1e293b]/30 rounded-lg p-2 border border-slate-700/30 shrink-0"
              style={
                isStacked || n === 1
                  ? { width: "100%", minWidth: 0 }
                  : { flex: "0 0 720px", width: 720, maxWidth: "calc(100vw - 220px)" }
              }
            >
              <FacetChart
                facet={facet}
                yAxisLabel={data.yAxisLabel}
                sharedYAxisMax={sharedYAxisMax}
                syncGroup={data.title}
                hiddenSeriesNames={hiddenSeriesNames}
                onLegendToggle={handleLegendToggle}
                inverted={inverted}
                chartHeight={facetChartHeight}
                showHighchartsLegend={
                  legendMode === "perFacet" && idx === 0
                }
                hoveredSeriesName={
                  useSharedLegendPanel ? effectiveLegendHover : null
                }
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
