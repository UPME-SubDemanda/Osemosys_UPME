import React, { useEffect, useMemo, useRef, useState } from "react";
import { FileDown } from "lucide-react";
import { useToast } from "@/app/providers/useToast";
import { simulationApi } from "@/features/simulation/api/simulationApi";
import { Button } from "@/shared/components/Button";
import { downloadBlob } from "@/shared/utils/downloadBlob";
import Highcharts from "./highchartsSetup";
import {
  EXPORTING_CONTEXT_BUTTON_DARK,
  HIGHCHARTS_GETSVG_MERGE_OPTIONS,
  INDIVIDUAL_CHART_EXPORT_MENU_ITEMS,
  onHighchartsExportError,
} from "./chartExportingShared";
import {
  buildCombinedFacetSvgDocument,
  extractSvgRootInnerXml,
  remapSvgFragmentIds,
} from "./mergeFacetChartsSvg";
import HighchartsReact from "highcharts-react-official";
import type {
  CompareChartFacetResponse,
  CompareFacetExportFilenameMode,
  FacetData,
} from "../../types/domain";
import type {
  ChartBarOrientation,
  ChartFacetLegendMode,
  ChartFacetPlacement,
} from "./chartLayoutPreferences";
import type { ChartSelection } from "./ChartSelector";

/** Título de leyenda en PNG servidor según agrupación (similar a la referencia de exportación). */
function safeExportBaseFromTitle(title: string, maxLen = 80): string {
  const clean = title.replace(/[^a-zA-Z0-9 _-]+/g, "_").replace(/_+/g, "_").trim();
  const base = clean || "grafico";
  return base.length > maxLen ? base.slice(0, maxLen) : base;
}

function compareFacetClientFilenameBase(
  data: CompareChartFacetResponse,
  mode: CompareFacetExportFilenameMode,
): string {
  const facets = data.facets.filter((f) => f.series?.length);
  if (facets.length === 0) {
    return safeExportBaseFromTitle(data.title);
  }
  const parts = facets.map((f) => {
    const simFb = (f.scenario_name || `job_${f.job_id}`).trim();
    const resultName = (f.display_name?.trim() || simFb).trim();
    if (mode === "tags") {
      const tag = f.scenario_tag_name?.trim() || "";
      return tag || resultName;
    }
    return resultName;
  });
  return safeExportBaseFromTitle(parts.join("__"), 140);
}

function facetExportLegendTitleFromSelection(sel: ChartSelection): string | undefined {
  const a = sel.agrupar_por?.toUpperCase();
  if (a === "FUEL" || a === "COMBUSTIBLE") return "Combustible / tecnología";
  if (a === "TECNOLOGIA") return "Tecnología";
  if (a === "GROUP") return "Familia / grupo";
  if (a === "SECTOR") return "Sector";
  return undefined;
}

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
  /** Si se define, permite descargar PNG (y parámetros) desde el backend sin Highcharts. */
  serverFacetExport?: {
    jobIds: number[];
    selection: ChartSelection;
    legendTitle?: string;
  };
}

/** Metadatos en la instancia Chart para exportar sin depender de un array de refs (getSVG / update rompen ese enlace). */
type HighchartsChartFacetExportMeta = Highcharts.Chart & {
  __facetSyncGroup?: string;
  __facetJobId?: number;
  __facetExportInstanceId?: string;
};

function resolveFacetChartsForExport(
  exportInstanceId: string,
  facets: FacetData[],
): Highcharts.Chart[] | null {
  const byJob = new Map<number, Highcharts.Chart>();
  for (const raw of Highcharts.charts) {
    if (!raw) continue;
    const c = raw as HighchartsChartFacetExportMeta;
    if (c.__facetExportInstanceId !== exportInstanceId || c.__facetJobId == null) continue;
    byJob.set(Number(c.__facetJobId), c);
  }
  const ordered: Highcharts.Chart[] = [];
  for (const f of facets) {
    const ch = byJob.get(Number(f.job_id));
    if (!ch) return null;
    ordered.push(ch);
  }
  return ordered;
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
  facetExportInstanceId,
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
  /** Id estable del bloque CompareChartFacet (marcado en cada Chart en `load`). */
  facetExportInstanceId: string;
}) {
  const chartRef = useRef<Highcharts.Chart | null>(null);
  const [chartGeneration, setChartGeneration] = useState(0);

  useEffect(() => {
    return () => {
      chartRef.current = null;
    };
  }, []);

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

    const simPart = facet.display_name?.trim() || facet.scenario_name;
    const tagPart = facet.scenario_tag_name?.trim();
    const facetTitleText = tagPart ? `${simPart} — ${tagPart}` : simPart;

    return {
      title: {
        text: facetTitleText,
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
            const ch = this as HighchartsChartFacetExportMeta;
            ch.__facetSyncGroup = syncGroup;
            ch.__facetJobId = facet.job_id;
            ch.__facetExportInstanceId = facetExportInstanceId;
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
            menuItems: [...INDIVIDUAL_CHART_EXPORT_MENU_ITEMS],
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
    facetExportInstanceId,
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
  serverFacetExport,
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
  /** Id único por montaje: cada Chart marca `__facetExportInstanceId` en `load` para resolver exportaciones desde `Highcharts.charts`. */
  const facetExportInstanceIdRef = useRef<string | null>(null);
  if (facetExportInstanceIdRef.current == null) {
    facetExportInstanceIdRef.current =
      globalThis.crypto?.randomUUID?.() ??
      `facet-export-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
  }
  const { push } = useToast();
  const [exportingFacetSvg, setExportingFacetSvg] = useState(false);
  const [exportingFacetPng, setExportingFacetPng] = useState(false);
  const [facetExportFilenameMode, setFacetExportFilenameMode] =
    useState<CompareFacetExportFilenameMode>("result");
  const exportBusy = exportingFacetSvg || exportingFacetPng;
  const exportFilenameSelectId = React.useId();

  const handleExportFacetPngServer = async () => {
    if (!serverFacetExport || serverFacetExport.jobIds.length < 2) {
      push("Se necesitan al menos dos escenarios seleccionados.", "error");
      return;
    }
    setExportingFacetPng(true);
    try {
      const sel = serverFacetExport.selection;
      const legend_title =
        serverFacetExport.legendTitle ?? facetExportLegendTitleFromSelection(sel);
      const payload: Parameters<typeof simulationApi.exportCompareFacet>[0] = {
        job_ids: serverFacetExport.jobIds.join(","),
        tipo: sel.tipo,
        un: sel.un,
      };
      if (sel.sub_filtro) payload.sub_filtro = sel.sub_filtro;
      if (sel.loc) payload.loc = sel.loc;
      if (sel.variable) payload.variable = sel.variable;
      if (sel.agrupar_por) payload.agrupar_por = sel.agrupar_por;
      if (legend_title) payload.legend_title = legend_title;
      payload.filename_mode = facetExportFilenameMode;
      const { blob, filename } = await simulationApi.exportCompareFacet(payload, "png");
      downloadBlob(blob, filename);
      push("PNG descargado (todas las facetas en una imagen).", "success");
    } catch (err) {
      console.error(err);
      push("No se pudo generar el PNG en el servidor.", "error");
    } finally {
      setExportingFacetPng(false);
    }
  };

  const handleExportCombinedSvg = () => {
    setExportingFacetSvg(true);
    try {
      const instanceId = facetExportInstanceIdRef.current;
      if (instanceId == null) {
        push("Espera a que todas las gráficas terminen de cargar.", "error");
        return;
      }
      const charts = resolveFacetChartsForExport(instanceId, data.facets);
      if (charts == null || charts.length !== n) {
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

      /** Evita que las etiquetas del eje Y queden pegadas al borde en facetas estrechas. */
      const yLabelCharEstimate = Math.max(
        7,
        String(Math.round(sharedYAxisMax > 0 ? sharedYAxisMax : 0)).length + 4,
      );
      const exportMarginLeft = Math.min(
        175,
        Math.max(108, Math.round(36 + yLabelCharEstimate * 10 + sliceW * 0.04)),
      );

      const innerXmls: string[] = [];
      for (let i = 0; i < n; i += 1) {
        const chart = charts[i]!;
        const raw = chart.getSVG({
          ...HIGHCHARTS_GETSVG_MERGE_OPTIONS,
          chart: {
            ...(HIGHCHARTS_GETSVG_MERGE_OPTIONS.chart as Record<string, unknown>),
            width: sliceW,
            height: sliceH,
            backgroundColor: "#FFFFFF",
            marginLeft: exportMarginLeft,
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
      const base = compareFacetClientFilenameBase(data, facetExportFilenameMode);
      const filename = `comparativa-facet-${base}-${new Date().toISOString().slice(0, 10)}.svg`;
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
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between lg:gap-4">
          <h3 className="m-0 min-w-0 flex-1 text-base font-bold text-slate-100" style={{ fontSize: "16px" }}>
            {data.title}
          </h3>
          <div className="flex w-full min-w-0 flex-wrap items-center justify-start gap-2 sm:justify-end lg:w-auto lg:flex-nowrap lg:shrink-0">
            {serverFacetExport && serverFacetExport.jobIds.length > 1 ? (
              <>
                <div className="flex min-w-0 max-w-full items-center gap-2">
                  <label
                    htmlFor={exportFilenameSelectId}
                    className="m-0 shrink-0 text-[10px] font-semibold uppercase tracking-wide text-slate-500"
                  >
                    Títulos de la gráfica
                  </label>
                  <select
                    id={exportFilenameSelectId}
                    value={facetExportFilenameMode}
                    onChange={(e) =>
                      setFacetExportFilenameMode(e.target.value as CompareFacetExportFilenameMode)
                    }
                    disabled={exportBusy}
                    className="h-9 min-w-[min(100%,12rem)] max-w-[min(100%,20rem)] shrink rounded-lg border border-slate-700 bg-slate-950 px-2.5 text-xs text-slate-200 disabled:opacity-50"
                  >
                    <option value="result">Nombre del resultado</option>
                    <option value="tags">Etiquetas (sin etiqueta → nombre del resultado)</option>
                  </select>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  disabled={exportBusy}
                  onClick={() => void handleExportFacetPngServer()}
                  className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-emerald-700/50 bg-emerald-950/40 px-3 py-2 text-xs font-semibold text-emerald-100 hover:border-emerald-600 hover:bg-emerald-900/50 disabled:opacity-50"
                >
                  <FileDown className="h-4 w-4 shrink-0" aria-hidden />
                  {exportingFacetPng ? "Generando PNG…" : "Descargar PNG (servidor)"}
                </Button>
              </>
            ) : null}
            <Button
              type="button"
              variant="ghost"
              disabled={exportBusy}
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
                  facetExportInstanceId={facetExportInstanceIdRef.current!}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
