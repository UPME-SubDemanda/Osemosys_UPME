/**
 * Data Explorer de resultados — vista wide de todas las variables persistidas
 * por una simulación. Replica la UX de ``/app/scenarios/:id`` (supuestos) pero
 * en solo-lectura sobre ``osemosys_output_param_value``.
 *
 * Endpoints: ``/simulations/{jobId}/output-values/wide``,
 * ``/simulations/{jobId}/output-values/wide/facets``,
 * ``/simulations/{jobId}/output-values/export``.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ColumnFilterPopover } from "@/shared/components/ColumnFilterPopover";
import { YearRuleFilterPopover } from "@/shared/components/YearRuleFilterPopover";
import { Button } from "@/shared/components/Button";
import { paths } from "@/routes/paths";
import { simulationApi } from "@/features/simulation/api/simulationApi";
import {
  resultsDataApi,
  serializeYearRules,
  type OutputValuesTotals,
  type OutputValueWideRow,
  type OutputWideFacets,
  type YearRule,
} from "@/features/results/api/resultsDataApi";
import {
  CATEGORIES,
  arraysEqualUnordered,
  resolveFuelNames,
  resolveTechnologyNames,
  type Category,
  type CategoryFilters,
  type SubCategory,
} from "@/features/results/categories";
import { CategoryTabs } from "@/features/results/components/CategoryTabs";
import {
  ColumnVisibilityPopover,
  type ColumnVisibilityMode,
} from "@/features/results/components/ColumnVisibilityPopover";

const PAGE_SIZE_OPTIONS = [25, 50, 100, 200] as const;

type DimFilterKey =
  | "variable_names"
  | "region_names"
  | "technology_names"
  | "fuel_names"
  | "emission_names"
  | "timeslice_names"
  | "mode_names"
  | "storage_names";

type DimHeader = {
  label: string;
  filterKey: DimFilterKey;
  facetKey: keyof OutputWideFacets;
  rowField: keyof OutputValueWideRow;
};

const DIM_HEADERS: DimHeader[] = [
  { label: "Variable", filterKey: "variable_names", facetKey: "variable_names", rowField: "variable_name" },
  { label: "Región", filterKey: "region_names", facetKey: "region_names", rowField: "region_name" },
  { label: "Tecnología", filterKey: "technology_names", facetKey: "technology_names", rowField: "technology_name" },
  { label: "Combustible", filterKey: "fuel_names", facetKey: "fuel_names", rowField: "fuel_name" },
  { label: "Emisión", filterKey: "emission_names", facetKey: "emission_names", rowField: "emission_name" },
  { label: "Timeslice", filterKey: "timeslice_names", facetKey: "timeslice_names", rowField: "timeslice_name" },
  { label: "Modo", filterKey: "mode_names", facetKey: "mode_names", rowField: "mode_name" },
  { label: "Almacenamiento", filterKey: "storage_names", facetKey: "storage_names", rowField: "storage_name" },
];

function formatCellValue(v: number): string {
  if (!Number.isFinite(v)) return "—";
  const abs = Math.abs(v);
  // Ruido numérico del solver: valores que redondean a 0 a 4 decimales
  // (incluye -0 IEEE-754 y negativos como -4e-5) se muestran como "0".
  if (abs < 5e-5) return (0).toLocaleString("es-CO");
  if (abs >= 1e6 || abs < 1e-3) return v.toExponential(3);
  return v.toLocaleString("es-CO", { maximumFractionDigits: 4 });
}

export function ResultDataExplorerPage() {
  const { runId } = useParams<{ runId: string }>();
  const jobId = useMemo(() => Number(runId), [runId]);

  const [jobLabel, setJobLabel] = useState<string>("");

  // Filtros por columna (dimensiones)
  const [columnFilters, setColumnFilters] = useState<Record<DimFilterKey, string[]>>({
    variable_names: [],
    region_names: [],
    technology_names: [],
    fuel_names: [],
    emission_names: [],
    timeslice_names: [],
    mode_names: [],
    storage_names: [],
  });

  // Reglas por año
  const [yearRules, setYearRules] = useState<Record<string, YearRule>>({});

  // Paginación
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(50);

  // Datos
  const [rows, setRows] = useState<OutputValueWideRow[]>([]);
  const [total, setTotal] = useState(0);
  const [years, setYears] = useState<number[]>([]);
  const [hasScalar, setHasScalar] = useState(false);

  const [facets, setFacets] = useState<OutputWideFacets | null>(null);
  const [facetsLoading, setFacetsLoading] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const [totals, setTotals] = useState<OutputValuesTotals | null>(null);

  // Cargar metadata del job para el título
  useEffect(() => {
    if (!Number.isFinite(jobId)) return;
    let cancelled = false;
    simulationApi
      .getRun(jobId)
      .then((run) => {
        if (cancelled) return;
        const name = run.display_name || run.scenario_name || `Simulación #${run.id}`;
        setJobLabel(String(name));
      })
      .catch(() => {
        if (!cancelled) setJobLabel(`Simulación #${jobId}`);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  const buildFilters = useCallback(() => {
    const f: Record<string, string[] | string | undefined> = {};
    for (const [k, v] of Object.entries(columnFilters)) {
      if (v && v.length) f[k] = v;
    }
    const yr = serializeYearRules(yearRules);
    if (yr) f.year_rules = yr;
    return f as Parameters<typeof resultsDataApi.listOutputValuesWide>[1];
  }, [columnFilters, yearRules]);

  // True cuando hay al menos un filtro activo de dimensión o año.
  const hasActiveFilters = useMemo(() => {
    if (Object.values(columnFilters).some((v) => v && v.length > 0)) return true;
    if (Object.keys(yearRules).length > 0) return true;
    return false;
  }, [columnFilters, yearRules]);

  // Cargar página
  useEffect(() => {
    if (!Number.isFinite(jobId)) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    const offset = (page - 1) * pageSize;
    resultsDataApi
      .listOutputValuesWide(jobId, { ...buildFilters(), offset, limit: pageSize })
      .then((resp) => {
        if (cancelled) return;
        setRows(resp.items);
        setTotal(resp.total);
        setYears(resp.years);
        setHasScalar(resp.has_scalar);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const msg = e instanceof Error ? e.message : "Error cargando resultados";
        setError(msg);
        setRows([]);
        setTotal(0);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId, page, pageSize, buildFilters]);

  // Cargar totales cuando hay filtros activos
  useEffect(() => {
    if (!Number.isFinite(jobId)) return;
    if (!hasActiveFilters) {
      setTotals(null);
      return;
    }
    let cancelled = false;
    resultsDataApi
      .getOutputTotals(jobId, buildFilters())
      .then((resp) => {
        if (!cancelled) setTotals(resp);
      })
      .catch(() => {
        if (!cancelled) setTotals(null);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId, hasActiveFilters, buildFilters]);

  // Cargar facets cuando cambien filtros (para auto-narrowing en popovers)
  useEffect(() => {
    if (!Number.isFinite(jobId)) return;
    let cancelled = false;
    setFacetsLoading(true);
    resultsDataApi
      .listOutputWideFacets(jobId, { ...buildFilters(), limit_per_column: 500 })
      .then((resp) => {
        if (!cancelled) setFacets(resp);
      })
      .catch(() => {
        if (!cancelled) setFacets(null);
      })
      .finally(() => {
        if (!cancelled) setFacetsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId, buildFilters]);

  const applyColumnFilter = useCallback(
    (key: DimFilterKey, next: string[]) => {
      setColumnFilters((prev) => ({ ...prev, [key]: next }));
      setPage(1);
    },
    [],
  );

  const applyYearRule = useCallback((year: number | string, rule: YearRule | null) => {
    setYearRules((prev) => {
      const next = { ...prev };
      const key = String(year);
      if (rule === null) delete next[key];
      else next[key] = rule;
      return next;
    });
    setPage(1);
  }, []);

  // ------------------------------------------------------------------
  //  Pestañas de categorías
  // ------------------------------------------------------------------
  const [activeCategory, setActiveCategory] = useState<string | null>("todos");
  const [activeSubCategory, setActiveSubCategory] = useState<string | null>(null);

  const buildColumnFiltersFromPreset = useCallback(
    (preset: CategoryFilters): Record<DimFilterKey, string[]> => {
      const empty: Record<DimFilterKey, string[]> = {
        variable_names: [],
        region_names: [],
        technology_names: [],
        fuel_names: [],
        emission_names: [],
        timeslice_names: [],
        mode_names: [],
        storage_names: [],
      };
      if (preset.variable_names?.length) {
        empty.variable_names = [...preset.variable_names];
      }
      if (preset.emission_names?.length) {
        empty.emission_names = [...preset.emission_names];
      }
      if (preset.technology_prefixes?.length && facets?.technology_names) {
        const resolved = resolveTechnologyNames(
          preset.technology_prefixes,
          facets.technology_names,
        );
        empty.technology_names = resolved;
      }
      return empty;
    },
    [facets],
  );

  const applyPreset = useCallback(
    (cat: Category, sub: SubCategory | null) => {
      const preset = sub?.filters ?? cat.filters;
      setColumnFilters(buildColumnFiltersFromPreset(preset));
      setYearRules({});
      setActiveCategory(cat.id);
      setActiveSubCategory(sub?.id ?? null);
      setPage(1);
    },
    [buildColumnFiltersFromPreset],
  );

  const handleSelectCategory = useCallback(
    (cat: Category) => {
      applyPreset(cat, null);
    },
    [applyPreset],
  );

  const handleSelectSubCategory = useCallback(
    (cat: Category, sub: SubCategory) => {
      applyPreset(cat, sub);
    },
    [applyPreset],
  );

  // Preset activo (madre + submadre) para derivar el universo de variables
  // disponible en el tercer nivel y manejar el click de "Todas".
  const activePresetFilters = useMemo<CategoryFilters>(() => {
    if (!activeCategory || activeCategory === "todos") return {};
    const cat = CATEGORIES.find((c) => c.id === activeCategory);
    if (!cat) return {};
    if (activeSubCategory) {
      const sub = cat.sub?.find((s) => s.id === activeSubCategory);
      return sub?.filters ?? cat.filters;
    }
    return cat.filters;
  }, [activeCategory, activeSubCategory]);

  // Gate: el tercer nivel sólo aparece cuando hay contexto de filtros activo.
  // - "Todos": nunca.
  // - Categoría con subs: requiere submadre seleccionada.
  // - Categoría sin subs (solo "Todos" hoy, ya filtrada): requiere madre.
  const thirdLevelAvailable = useMemo(() => {
    if (!activeCategory || activeCategory === "todos") return false;
    const cat = CATEGORIES.find((c) => c.id === activeCategory);
    if (!cat) return false;
    if (cat.sub && cat.sub.length > 0) return activeSubCategory != null;
    return true;
  }, [activeCategory, activeSubCategory]);

  // Variables que aparecen como pills en el tercer nivel:
  //  1. Se calculan vía dos llamadas a facets: una con el filtro de tecnología
  //     del preset activo y otra con el filtro de combustible (si aplica).
  //  2. Se unen (variable tiene valores bajo tech OR fuel).
  //  3. Se intersectan con `preset.variable_names` si el preset restringe.
  const [thirdLevelVars, setThirdLevelVars] = useState<string[]>([]);

  useEffect(() => {
    if (!Number.isFinite(jobId) || !thirdLevelAvailable) {
      setThirdLevelVars([]);
      return;
    }
    let cancelled = false;

    const fetchAll = async () => {
      const presetFuelNames =
        activePresetFilters.fuel_prefixes && facets?.fuel_names
          ? resolveFuelNames(
              activePresetFilters.fuel_prefixes,
              facets.fuel_names,
            )
          : [];

      const presetTechNames =
        activePresetFilters.technology_prefixes && facets?.technology_names
          ? resolveTechnologyNames(
              activePresetFilters.technology_prefixes,
              facets.technology_names,
            )
          : [];

      const baseFilters: Record<string, string[] | string | undefined> = {};
      // Reutiliza dimensiones distintas a tech/fuel (p.ej. region, emission)
      for (const [k, v] of Object.entries(columnFilters)) {
        if (k === "technology_names" || k === "fuel_names") continue;
        if (v && v.length) baseFilters[k] = v;
      }
      const yr = serializeYearRules(yearRules);
      if (yr) baseFilters.year_rules = yr;

      const call = (extra: Record<string, string[]>) =>
        resultsDataApi
          .listOutputWideFacets(jobId, {
            ...baseFilters,
            ...extra,
            limit_per_column: 500,
          })
          .then((r) => r.variable_names ?? [])
          .catch(() => [] as string[]);

      const queries: Promise<string[]>[] = [];
      if (presetTechNames.length > 0) {
        queries.push(call({ technology_names: presetTechNames }));
      }
      if (presetFuelNames.length > 0) {
        queries.push(call({ fuel_names: presetFuelNames }));
      }
      if (queries.length === 0) {
        // Categoría sin tech/fuel prefixes (p.ej. Emisiones) — usa facets del
        // estado actual (ya filter-aware en backend).
        queries.push(call({}));
      }

      const results = await Promise.all(queries);
      const union = new Set<string>();
      for (const list of results) for (const v of list) union.add(v);

      let options = Array.from(union);
      // Si el preset restringe variables, sólo muestra las de la lista.
      const presetVars = activePresetFilters.variable_names;
      if (presetVars && presetVars.length > 0) {
        const allowed = new Set(presetVars);
        options = options.filter((v) => allowed.has(v));
      }
      options.sort();
      if (!cancelled) setThirdLevelVars(options);
    };

    void fetchAll();
    return () => {
      cancelled = true;
    };
  }, [
    jobId,
    thirdLevelAvailable,
    activePresetFilters,
    columnFilters,
    yearRules,
    facets?.technology_names,
    facets?.fuel_names,
  ]);

  // ------------------------------------------------------------------
  //  Pre-carga de filtros desde la URL (llegada desde una gráfica)
  // ------------------------------------------------------------------
  const [searchParams, setSearchParams] = useSearchParams();
  const appliedUrlRef = useRef<string | null>(null);

  useEffect(() => {
    const qs = searchParams.toString();
    if (!qs) return;
    // Esperar a que facets estén disponibles para resolver prefijos.
    if (!facets) return;
    // Aplicar sólo una vez por querystring distinto.
    if (appliedUrlRef.current === qs) return;

    const csv = (key: string): string[] => {
      const v = searchParams.get(key);
      if (!v) return [];
      return v.split(",").map((s) => s.trim()).filter(Boolean);
    };

    const varNames = csv("variable_names");
    const techPrefixes = csv("technology_prefixes");
    const fuelPrefixes = csv("fuel_prefixes");
    const emissionNames = csv("emission_names");

    const resolvedTech = techPrefixes.length
      ? resolveTechnologyNames(techPrefixes, facets.technology_names ?? [])
      : [];
    const resolvedFuel = fuelPrefixes.length
      ? resolveFuelNames(fuelPrefixes, facets.fuel_names ?? [])
      : [];

    const nextFilters: Record<DimFilterKey, string[]> = {
      variable_names: varNames,
      region_names: [],
      technology_names: resolvedTech,
      fuel_names: resolvedFuel,
      emission_names: emissionNames,
      timeslice_names: [],
      mode_names: [],
      storage_names: [],
    };
    setColumnFilters(nextFilters);
    setYearRules({});
    setActiveCategory(null);
    setActiveSubCategory(null);
    setPage(1);
    appliedUrlRef.current = qs;

    // Limpiar querystring después de aplicar para que refrescos subsecuentes
    // no re-sobrescriban la selección manual del usuario.
    setSearchParams({}, { replace: true });
  }, [searchParams, facets, setSearchParams]);

  const handleSelectVariable = useCallback(
    (v: string | null) => {
      if (v !== null) {
        applyColumnFilter("variable_names", [v]);
        return;
      }
      // "Todas" — restaurar al preset activo (o limpiar si no hay restricción).
      const presetVars = activePresetFilters.variable_names ?? [];
      applyColumnFilter("variable_names", [...presetVars]);
    },
    [activePresetFilters, applyColumnFilter],
  );

  // Des-selecciona la sub-categoría si el usuario edita manualmente los
  // filtros y dejan de coincidir con el preset activo. El tercer nivel
  // (selector de variable) puede NARROW `variable_names` a un subconjunto
  // del preset sin des-activar la madre/submadre.
  useEffect(() => {
    if (!activeCategory || activeCategory === "todos") return;
    const cat = CATEGORIES.find((c) => c.id === activeCategory);
    if (!cat) return;
    const activeSub = activeSubCategory
      ? cat.sub?.find((s) => s.id === activeSubCategory)
      : null;

    const matches = (presetFilters: CategoryFilters): boolean => {
      const expected = buildColumnFiltersFromPreset(presetFilters);
      // Todas las dims excepto variable_names deben coincidir exacto.
      const nonVarKeys: DimFilterKey[] = [
        "region_names",
        "technology_names",
        "fuel_names",
        "emission_names",
        "timeslice_names",
        "mode_names",
        "storage_names",
      ];
      for (const k of nonVarKeys) {
        if (!arraysEqualUnordered(expected[k], columnFilters[k] ?? [])) {
          return false;
        }
      }
      // variable_names: si el preset restringe, el actual debe ser
      // igual o subconjunto no-vacío de esa lista. Si el preset no
      // restringe, cualquier variable_names es aceptable.
      const presetVars = presetFilters.variable_names ?? [];
      const currVars = columnFilters.variable_names ?? [];
      if (presetVars.length === 0) return true;
      if (currVars.length === 0) return false;
      const presetSet = new Set(presetVars);
      return currVars.every((v) => presetSet.has(v));
    };

    const subMatch = activeSub ? matches(activeSub.filters) : true;
    if (activeSub && !subMatch) {
      setActiveSubCategory(null);
    }
    if (!matches(cat.filters) && !activeSub) {
      setActiveCategory(null);
    }
  }, [columnFilters, activeCategory, activeSubCategory, buildColumnFiltersFromPreset]);

  // ------------------------------------------------------------------
  //  Visibilidad de columnas
  // ------------------------------------------------------------------
  const [columnModes, setColumnModes] = useState<Record<string, ColumnVisibilityMode>>({});
  const [autoHideEnabled, setAutoHideEnabled] = useState(true);

  const dimIsEmpty = useCallback(
    (h: DimHeader): boolean => {
      if (rows.length === 0) return false; // sin datos: no ocultamos aún
      return rows.every((r) => {
        const v = r[h.rowField];
        return v == null || v === "";
      });
    },
    [rows],
  );

  const isColumnVisible = useCallback(
    (id: string, emptyInCurrentPage: boolean): boolean => {
      const mode = columnModes[id] ?? "auto";
      if (mode === "visible") return true;
      if (mode === "hidden") return false;
      // auto
      if (autoHideEnabled && emptyInCurrentPage) return false;
      return true;
    },
    [columnModes, autoHideEnabled],
  );

  const visibleDimHeaders = useMemo(
    () => DIM_HEADERS.filter((h) => isColumnVisible(h.filterKey, dimIsEmpty(h))),
    [isColumnVisible, dimIsEmpty],
  );

  const handleColumnModeChange = useCallback(
    (id: string, mode: ColumnVisibilityMode) => {
      setColumnModes((prev) => {
        if (mode === "auto") {
          const next = { ...prev };
          delete next[id];
          return next;
        }
        return { ...prev, [id]: mode };
      });
    },
    [],
  );

  const handleResetColumnModes = useCallback(() => setColumnModes({}), []);

  const handleExport = useCallback(async () => {
    if (!Number.isFinite(jobId)) return;
    setExporting(true);
    try {
      const blob = await resultsDataApi.exportOutputValues(jobId, buildFilters());
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `simulation_${jobId}_results.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Error exportando";
      setError(msg);
    } finally {
      setExporting(false);
    }
  }, [jobId, buildFilters]);

  const selectedYearsSet = useMemo(() => {
    return new Set(Object.keys(yearRules));
  }, [yearRules]);

  const yearsShown = useMemo(() => {
    if (selectedYearsSet.size > 0) {
      return years.filter((y) => selectedYearsSet.has(String(y)));
    }
    return years;
  }, [years, selectedYearsSet]);

  // Escalar se oculta si hay selección explícita de años
  const scalarShown = hasScalar && selectedYearsSet.size === 0;

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const totalCols =
    visibleDimHeaders.length + (scalarShown ? 1 : 0) + yearsShown.length;

  return (
    <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link
            to={paths.results}
            style={{
              fontSize: 13,
              color: "var(--muted)",
              textDecoration: "none",
            }}
          >
            ← Resultados
          </Link>
          <h2 style={{ margin: 0, fontSize: 18 }}>
            Data Explorer
            {jobLabel ? (
              <span style={{ opacity: 0.65, fontWeight: 400, marginLeft: 8 }}>
                · {jobLabel}
              </span>
            ) : null}
          </h2>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <ColumnVisibilityPopover
            columns={DIM_HEADERS.map((h) => ({
              id: h.filterKey,
              label: h.label,
              isEmpty: dimIsEmpty(h),
            }))}
            modes={columnModes}
            autoHideEnabled={autoHideEnabled}
            onChangeMode={handleColumnModeChange}
            onToggleAutoHide={setAutoHideEnabled}
            onResetAll={handleResetColumnModes}
          />
          <Button onClick={handleExport} disabled={exporting || loading}>
            {exporting ? "Generando Excel…" : "Exportar a Excel"}
          </Button>
        </div>
      </div>

      <CategoryTabs
        categories={CATEGORIES}
        activeCategory={activeCategory}
        activeSubCategory={activeSubCategory}
        onSelectCategory={handleSelectCategory}
        onSelectSubCategory={handleSelectSubCategory}
        variableOptions={thirdLevelAvailable ? thirdLevelVars : undefined}
        activeVariable={
          columnFilters.variable_names.length === 1
            ? columnFilters.variable_names[0] ?? null
            : null
        }
        onSelectVariable={thirdLevelAvailable ? handleSelectVariable : undefined}
      />

      {error ? (
        <div
          role="alert"
          style={{
            padding: "8px 12px",
            background: "rgba(255, 90, 90, 0.08)",
            border: "1px solid rgba(255, 90, 90, 0.3)",
            borderRadius: 6,
            fontSize: 13,
            color: "rgba(255, 180, 180, 0.95)",
          }}
        >
          {error}
        </div>
      ) : null}

      <div style={{ overflowX: "auto", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12 }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead style={{ background: "rgba(255,255,255,0.03)" }}>
            <tr>
              {visibleDimHeaders.map((h) => (
                <th
                  key={h.label}
                  style={{
                    textAlign: "left",
                    fontSize: 13,
                    padding: "8px 10px",
                    color: "var(--muted)",
                    position: "sticky",
                    top: 0,
                    background: "rgba(20,20,24,0.95)",
                    whiteSpace: "nowrap",
                  }}
                >
                  <span style={{ display: "inline-flex", alignItems: "center" }}>
                    {h.label}
                    <ColumnFilterPopover
                      columnLabel={h.label}
                      options={(facets?.[h.facetKey] ?? []) as string[]}
                      selected={columnFilters[h.filterKey] ?? []}
                      loading={facetsLoading}
                      onChange={(next) => applyColumnFilter(h.filterKey, next)}
                    />
                  </span>
                </th>
              ))}
              {scalarShown ? (
                <th
                  style={{
                    textAlign: "right",
                    fontSize: 13,
                    padding: "10px 12px",
                    color: "var(--muted)",
                    background: "rgba(20,20,24,0.95)",
                  }}
                >
                  Valor (no temporal)
                </th>
              ) : null}
              {yearsShown.map((y) => (
                <th
                  key={y}
                  style={{
                    textAlign: "right",
                    fontSize: 13,
                    padding: "8px 10px",
                    color: "var(--muted)",
                    background: "rgba(20,20,24,0.95)",
                    whiteSpace: "nowrap",
                  }}
                >
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 2 }}>
                    {y}
                    <YearRuleFilterPopover
                      year={y}
                      rule={yearRules[String(y)] ?? null}
                      onChange={(r) => applyYearRule(y, r)}
                    />
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && rows.length === 0 ? (
              <tr>
                <td colSpan={totalCols} style={{ padding: 14, opacity: 0.75 }}>
                  Cargando…
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={totalCols} style={{ padding: 14, opacity: 0.75 }}>
                  Sin registros.
                </td>
              </tr>
            ) : (
              rows.map((g) => {
                const cellKeys: string[] = [];
                if (scalarShown) cellKeys.push("scalar");
                for (const y of yearsShown) cellKeys.push(String(y));
                return (
                  <tr key={g.group_key} style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                    {visibleDimHeaders.map((h) => {
                      const v = g[h.rowField];
                      return (
                        <td key={h.label} style={{ padding: "4px 10px", fontSize: 13 }}>
                          {v == null || v === "" ? "—" : String(v)}
                        </td>
                      );
                    })}
                    {cellKeys.map((yearKey) => {
                      const cell = g.cells[yearKey];
                      return (
                        <td
                          key={yearKey}
                          style={{
                            padding: "2px 8px",
                            textAlign: "right",
                            fontSize: 13,
                            fontVariantNumeric: "tabular-nums",
                          }}
                          title={cell ? `Valor: ${cell.value}` : "Sin valor"}
                        >
                          {cell ? (
                            formatCellValue(cell.value)
                          ) : (
                            <span style={{ opacity: 0.35 }}>—</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })
            )}
            {hasActiveFilters && totals && page === totalPages && rows.length > 0 ? (
              <tr
                style={{
                  borderTop: "2px solid rgba(80,140,255,0.35)",
                  background: "rgba(80,140,255,0.06)",
                  fontWeight: 600,
                }}
              >
                {visibleDimHeaders.map((h, i) => (
                  <td
                    key={h.label}
                    style={{
                      padding: "6px 10px",
                      fontSize: 13,
                      color: "rgba(220,230,255,0.95)",
                    }}
                  >
                    {i === 0 ? `Total (${totals.row_count.toLocaleString("es-CO")} filas)` : ""}
                  </td>
                ))}
                {scalarShown ? (
                  <td
                    style={{
                      padding: "6px 10px",
                      textAlign: "right",
                      fontSize: 13,
                      fontVariantNumeric: "tabular-nums",
                      color: "rgba(220,230,255,0.95)",
                    }}
                  >
                    {totals.scalar != null ? formatCellValue(totals.scalar) : "—"}
                  </td>
                ) : null}
                {yearsShown.map((y) => {
                  const v = totals.years[String(y)];
                  return (
                    <td
                      key={y}
                      style={{
                        padding: "6px 10px",
                        textAlign: "right",
                        fontSize: 13,
                        fontVariantNumeric: "tabular-nums",
                        color: "rgba(220,230,255,0.95)",
                      }}
                    >
                      {v != null ? formatCellValue(v) : "—"}
                    </td>
                  );
                })}
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <small style={{ opacity: 0.75 }}>
            Página {page} de {totalPages} · {total.toLocaleString("es-CO")}{" "}
            {total === 1 ? "grupo" : "grupos"}
          </small>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12 }}>
            Filas por página
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              style={{
                background: "transparent",
                color: "inherit",
                border: "1px solid rgba(255,255,255,0.12)",
                borderRadius: 4,
                padding: "2px 6px",
              }}
            >
              {PAGE_SIZE_OPTIONS.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <Button
            variant="ghost"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1 || loading}
          >
            ←
          </Button>
          <Button
            variant="ghost"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages || loading}
          >
            →
          </Button>
        </div>
      </div>
    </div>
  );
}

export default ResultDataExplorerPage;
