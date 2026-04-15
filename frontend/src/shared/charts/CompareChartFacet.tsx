import React, { useEffect, useMemo, useRef, useState } from "react";
import { FileDown } from "lucide-react";
import { useToast } from "@/app/providers/useToast";
import { Button } from "@/shared/components/Button";
import { downloadBlob } from "@/shared/utils/downloadBlob";
import Highcharts from "./highchartsSetup";
import {
  EXPORTING_CONTEXT_BUTTON_DARK,
  HIGHCHARTS_GETSVG_MERGE_OPTIONS,
  onHighchartsExportError,
} from "./chartExportingShared";
import {
  buildCombinedFacetSvgDocument,
  extractSvgRootInnerXml,
  remapSvgFragmentIds,
} from "./mergeFacetChartsSvg";
import HighchartsReact from "highcharts-react-official";
import type { CompareChartFacetResponse, FacetData } from "../../types/domain";
import type {
  ChartBarOrientation,
  ChartFacetLegendMode,
  ChartFacetPlacement,
} from "./chartLayoutPreferences";

function stackLabelFormatter(this: Highcharts.StackItemObject): string {
  return Highcharts.numberFormat(this.total, 2, ".", ",");
}

/** Tamaño de fuente de categorías en eje X (barras verticales). */
const FACET_X_LABEL_FONT_PX = 16;
/** Etiquetas del eje Y (valores) en pantalla. */
const FACET_Y_LABEL_FONT_PX = 14;

function maxCategoryCharLength(categories: string[]): number {
  if (categories.length === 0) return 1;
  return Math.max(1, ...categories.map((c) => String(c).length));
}

/**
 * Margen inferior para etiquetas en vertical: escala con la etiqueta más larga y el tamaño de fuente.
 */
function facetMarginBottomForVerticalCategoryLabels(
  categories: string[],
  fontPx: number,
): number {
  const len = maxCategoryCharLength(categories);
  const perChar = fontPx * 0.62;
  return Math.round(Math.min(32 + len * perChar, 300));
}

function useMediaMinWidth(px: number): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia(`(min-width: ${px}px)`).matches : false,
  );
  useEffect(() => {
    const mq = window.matchMedia(`(min-width: ${px}px)`);
    const onChange = () => setMatches(mq.matches);
    onChange();
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [px]);
  return matches;
}

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
  facetChartIndex,
  facetChartsRef,
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
  facetChartIndex: number;
  facetChartsRef: React.MutableRefObject<(Highcharts.Chart | null)[]>;
}) {
  const chartRef = useRef<Highcharts.Chart | null>(null);
  const [chartGeneration, setChartGeneration] = useState(0);

  useEffect(() => {
    const idx = facetChartIndex;
    return () => {
      facetChartsRef.current[idx] = null; // eslint-disable-line react-hooks/exhaustive-deps -- leer .current al desmontar
    };
  }, [facetChartIndex, facetChartsRef]);

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
      borderWidth: 0,
    }));

    const marginBottomVert = !inverted
      ? facetMarginBottomForVerticalCategoryLabels(facet.categories, FACET_X_LABEL_FONT_PX)
      : undefined;

    return {
      title: {
        text: facet.scenario_name,
        style: { fontSize: "14px", fontWeight: "bold", color: "#f8fafc" },
      },
      xAxis: {
        categories: facet.categories,
        crosshair: { color: "#334155" },
        lineWidth: 1,
        tickWidth: 1,
        labels: (
          inverted
            ? {
                style: { color: "#94a3b8", fontSize: `${FACET_X_LABEL_FONT_PX}px` },
                autoRotation: false,
              }
            : {
                rotation: -90,
                align: "right",
                x: 4,
                y: -2,
                reserveSpace: true,
                autoRotation: false,
                style: {
                  color: "#94a3b8",
                  fontSize: `${FACET_X_LABEL_FONT_PX}px`,
                  whiteSpace: "nowrap",
                },
              }
        ) as unknown as Highcharts.XAxisLabelsOptions,
        lineColor: "#64748b",
        tickColor: "#64748b",
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
        lineWidth: 1,
        lineColor: "#64748b",
        title: {
          text: yAxisLabel,
          style: { color: "#94a3b8", fontSize: `${FACET_Y_LABEL_FONT_PX + 1}px` },
        },
        labels: { style: { color: "#94a3b8", fontSize: `${FACET_Y_LABEL_FONT_PX}px` } },
        gridLineColor: "#334155",
        stackLabels: {
          enabled: true,
          style: {
            fontWeight: "bold",
            color: "#94a3b8",
            textOutline: "none",
            fontSize: "12px",
          },
          formatter: stackLabelFormatter,
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
        column: {
          stacking: "normal",
          borderWidth: 0,
          groupPadding: 0.08,
          dataLabels: { enabled: false },
        },
      },
      series: series as Highcharts.SeriesOptionsType[],
      chart: {
        type: "column",
        height: chartHeight,
        inverted,
        ...(marginBottomVert !== undefined ? { marginBottom: marginBottomVert } : {}),
        style: { fontFamily: "Verdana, sans-serif" },
        backgroundColor: "transparent",
        borderWidth: 0,
        plotBorderWidth: 1,
        plotBorderColor: "rgba(148, 163, 184, 0.45)",
        plotShadow: false,
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
        chartOptions: HIGHCHARTS_GETSVG_MERGE_OPTIONS as Highcharts.Options,
        buttons: {
          contextButton: {
            menuItems: ["downloadSVG"],
            ...EXPORTING_CONTEXT_BUTTON_DARK,
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
        facetChartsRef.current[facetChartIndex] = chart;
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
      return Math.min(640, 240 + catLen * 15);
    }
    // Altura algo menor; el margen inferior dinámico reserva sitio para etiquetas verticales.
    if (n >= 4) return 320;
    if (n >= 3) return 335;
    return 360;
  }, [data.facets, inverted, n]);

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
  const isLg = useMediaMinWidth(1024);
  const facetChartsRef = useRef<(Highcharts.Chart | null)[]>([]);
  if (facetChartsRef.current.length !== n) {
    const prev = facetChartsRef.current;
    facetChartsRef.current = Array.from({ length: n }, (_, i) => prev[i] ?? null);
  }
  const { push } = useToast();
  const [exportingFacetSvg, setExportingFacetSvg] = useState(false);

  const handleExportCombinedSvg = () => {
    setExportingFacetSvg(true);
    try {
      const refs = facetChartsRef.current;
      if (refs.length !== n || refs.some((c) => !c)) {
        push("Espera a que todas las gráficas terminen de cargar.", "error");
        return;
      }
      const layout = isStacked ? "column" : "row";
      const totalBaseW = 1920;
      let sliceW: number;
      let sliceH: number;
      if (layout === "row") {
        const padding = 24 * 2;
        const gaps = Math.max(0, n - 1) * 16;
        sliceW = Math.floor((totalBaseW - padding - gaps) / n);
        sliceH = 1080;
      } else {
        sliceW = totalBaseW - 48;
        sliceH = Math.floor((1080 - Math.max(0, n - 1) * 16) / Math.max(n, 1));
      }

      const exportXLabelPx = 24;
      const maxCatLenExport = Math.max(
        ...data.facets.map((f) => maxCategoryCharLength(f.categories)),
        1,
      );
      const exportMarginBottom = !inverted
        ? Math.round(Math.min(44 + maxCatLenExport * exportXLabelPx * 0.62, 340))
        : undefined;

      const innerXmls: string[] = [];
      for (let i = 0; i < n; i += 1) {
        const chart = refs[i]!;
        const raw = chart.getSVG({
          ...HIGHCHARTS_GETSVG_MERGE_OPTIONS,
          chart: {
            ...(HIGHCHARTS_GETSVG_MERGE_OPTIONS.chart as Record<string, unknown>),
            width: sliceW,
            height: sliceH,
            backgroundColor: "#FFFFFF",
            ...(exportMarginBottom !== undefined ? { marginBottom: exportMarginBottom } : {}),
          },
          exporting: {
            sourceWidth: sliceW,
            sourceHeight: sliceH,
          },
          ...(!inverted
            ? {
                xAxis: {
                  labels: {
                    rotation: -90,
                    align: "right",
                    reserveSpace: true,
                    autoRotation: false,
                    style: { color: "#334155", fontSize: `${exportXLabelPx}px` },
                  } as unknown as Highcharts.XAxisLabelsOptions,
                  lineWidth: 1,
                  lineColor: "#334155",
                  tickWidth: 1,
                  tickColor: "#334155",
                },
                yAxis: {
                  lineWidth: 1,
                  lineColor: "#334155",
                },
              }
            : {}),
        } as Highcharts.Options);
        const fixed = i === 0 ? raw : remapSvgFragmentIds(raw, `f${i}_`);
        innerXmls.push(extractSvgRootInnerXml(fixed));
      }

      const exportLegendItems =
        sharedLegendItems.length > 0
          ? sharedLegendItems.map(({ name, color }) => ({
              name,
              color,
              hidden: hiddenSeriesNames.has(name),
            }))
          : undefined;

      const doc = buildCombinedFacetSvgDocument({
        mainTitle: data.title,
        fragmentInnerXmls: innerXmls,
        layout,
        sliceW,
        sliceH,
        ...(exportLegendItems ? { legendItems: exportLegendItems } : {}),
      });
      const safe = data.title
        .replace(/[^a-zA-Z0-9]+/g, "-")
        .replace(/^-|-$/g, "")
        .slice(0, 80);
      const filename = `comparativa-facet-${safe || "graficos"}-${new Date().toISOString().slice(0, 10)}.svg`;
      downloadBlob(new Blob([doc], { type: "image/svg+xml;charset=utf-8" }), filename);
      push("SVG combinado descargado (misma apariencia que exportar una gráfica).", "success");
    } catch (err) {
      console.error(err);
      push("No se pudo generar el SVG combinado.", "error");
    } finally {
      setExportingFacetSvg(false);
    }
  };

  return (
    <div className="w-full space-y-4">
      <div className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <h3 className="m-0 min-w-0 text-base font-bold text-slate-100" style={{ fontSize: "16px" }}>
            {data.title}
          </h3>
          <div>
            <Button
              type="button"
              variant="ghost"
              disabled={exportingFacetSvg}
              onClick={handleExportCombinedSvg}
              className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-slate-700 bg-slate-900/60 px-3 py-2 text-xs font-semibold text-slate-200 hover:border-slate-600 hover:bg-slate-800/80 disabled:opacity-50"
            >
              <FileDown className="h-4 w-4 shrink-0" aria-hidden />
              {exportingFacetSvg ? "Generando SVG…" : "Descargar SVG (todas las facetas)"}
            </Button>
          </div>
        </div>
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
        <div className="w-full pb-2">
          <div
            className={
              isStacked
                ? "flex w-full flex-col gap-4"
                : "grid w-full gap-4"
            }
            style={
              isStacked
                ? undefined
                : {
                    gridTemplateColumns:
                      n === 1 || !isLg ? "minmax(0, 1fr)" : `repeat(${n}, minmax(0, 1fr))`,
                  }
            }
          >
            {data.facets.map((facet, idx) => (
              <div
                key={facet.job_id}
                className="min-w-0 rounded-lg border border-slate-800/80 bg-[#1e293b]/30 p-2"
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
                  facetChartIndex={idx}
                  facetChartsRef={facetChartsRef}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
