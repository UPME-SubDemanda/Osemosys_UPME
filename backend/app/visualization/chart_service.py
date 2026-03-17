"""Chart service — lógica central de visualización.

Reemplaza ``graficas.py`` y ``graficas_comparacion.py`` del paquete
``osemosys_src`` para funcionar directamente contra la BD.  Cada función
pública devuelve un Pydantic schema listo para serialización en FastAPI.

Funciones públicas:
  - ``build_chart_data``       → gráfica single-escenario
  - ``build_comparison_data``  → gráfica multi-escenario / subplots por año
  - ``get_result_summary``     → KPIs de cabecera
  - ``get_chart_catalog``      → catálogo de tipos de gráfica disponibles
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import OsemosysOutputParamValue, SimulationJob
from app.schemas.visualization import (
    ChartCatalogItem,
    ChartDataResponse,
    ChartSeries,
    CompareChartFacetResponse,
    CompareChartResponse,
    FacetData,
    ResultSummaryResponse,
    SubplotData,
)
from app.visualization.colors import (
    COLORES_GRUPOS,
    asignar_grupo,
    generar_colores_tecnologias,
    _color_electricidad,
    _color_por_grupo_fijo,
)
from app.visualization.configs import CONFIGS, TITULOS_VARIABLES_CAPACIDAD
from app.visualization.configs_comparacion import (
    COLORES_SECTOR,
    CONFIGS_COMPARACION,
    MAPA_SECTOR,
)

logger = logging.getLogger(__name__)

# Variables principales (columnas tipadas en la BD)
_MAIN_TYPED_VARIABLES = {"Dispatch", "NewCapacity", "UnmetDemand", "AnnualEmissions"}


# ═══════════════════════════════════════════════════════════════════════════
# 1. DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════

def _load_variable_data(
    db: Session,
    job_id: int,
    variable_name: str,
) -> pd.DataFrame:
    """Carga datos de ``osemosys_output_param_value`` y devuelve un DataFrame.

    • Variables principales (Dispatch, NewCapacity, …): usa columnas tipadas
      (``technology_name``, ``fuel_name``, ``year``, ``value``).
    • Variables intermedias (ProductionByTechnology, TotalCapacityAnnual, …):
      extrae TECHNOLOGY, FUEL, YEAR del campo ``index_json``.

    Parámetros
    ----------
    db : Session
        Sesión SQLAlchemy activa.
    job_id : int
        ID del simulation_job.
    variable_name : str
        Nombre exacto de la variable a cargar.

    Retorna
    -------
    pd.DataFrame
        Columnas garantizadas: TECHNOLOGY, YEAR, VALUE.
        Columna opcional: FUEL (cuando está disponible).
    """

    # ── Consulta BD ──────────────────────────────────────────────────────
    rows = (
        db.query(OsemosysOutputParamValue)
        .filter(
            OsemosysOutputParamValue.id_simulation_job == job_id,
            OsemosysOutputParamValue.variable_name == variable_name,
        )
        .all()
    )

    if not rows:
        return pd.DataFrame(columns=["TECHNOLOGY", "FUEL", "YEAR", "VALUE"])

    # ── Construir DataFrame ──────────────────────────────────────────────
    if variable_name in _MAIN_TYPED_VARIABLES:
        records = []
        for r in rows:
            records.append({
                "TECHNOLOGY": r.technology_name or "",
                "FUEL": r.fuel_name or "",
                "YEAR": r.year,
                "VALUE": float(r.value),
            })
        df = pd.DataFrame(records)

    else:
        # Variable intermedia → extraer de index_json
        records = []
        for r in rows:
            idx = r.index_json if r.index_json else []
            # Convenciones del pipeline:
            #   ProductionByTechnology / UseByTechnology / TotalCapacityAnnual /
            #   AccumulatedNewCapacity / AnnualTechnologyEmission:
            #     index_json = [REGION, TECHNOLOGY, FUEL?, YEAR?, ...]
            # La posición del YEAR puede variar: posición 2, 3 o 4.
            technology = str(idx[1]) if len(idx) > 1 else ""
            fuel = ""
            year = None

            if len(idx) >= 5:
                # [REGION, TECH, FUEL, ?, YEAR]  (5-element index)
                fuel = str(idx[2]) if idx[2] is not None else ""
                year = _safe_int(idx[4]) or _safe_int(idx[3])
            elif len(idx) >= 4:
                # [REGION, TECH, FUEL, YEAR]  (4-element index)
                fuel = str(idx[2]) if idx[2] is not None else ""
                year = _safe_int(idx[3])
            elif len(idx) >= 3:
                # [REGION, TECH, YEAR]  (3-element index)
                year = _safe_int(idx[2])

            records.append({
                "TECHNOLOGY": technology,
                "FUEL": fuel,
                "YEAR": year,
                "VALUE": float(r.value),
            })
        df = pd.DataFrame(records)

    # Limpiar: descartar filas sin YEAR útil
    df = df.dropna(subset=["YEAR"])
    df["YEAR"] = df["YEAR"].astype(int)

    return df


def _safe_int(val: Any) -> int | None:
    """Intenta convertir un valor a int, retorna None si falla."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


# ═══════════════════════════════════════════════════════════════════════════
# 2. HELPERS DE TRANSFORMACIÓN (ports de graficas_comparacion.py)
# ═══════════════════════════════════════════════════════════════════════════

def _filtrar_df(
    df: pd.DataFrame,
    prefijo: str | tuple[str, ...],
    sub_filtro: str | None,
    loc: str | None,
) -> pd.DataFrame:
    """Aplica filtro por prefijo de TECHNOLOGY, sub_filtro y localización.

    Port directo de ``graficas_comparacion._filtrar_df``.
    """
    if df.empty:
        return df

    df = df[df["TECHNOLOGY"].str.startswith(prefijo)].copy()

    if sub_filtro:
        df = df[df["TECHNOLOGY"].str.contains(sub_filtro)]

    if loc == "URB":
        df = df[~df["TECHNOLOGY"].str.contains("RUR")]
        df = df[~df["TECHNOLOGY"].str.contains("ZNI")]
    elif loc == "RUR":
        df = df[df["TECHNOLOGY"].str.contains("RUR")]
        df = df[~df["TECHNOLOGY"].str.contains("ZNI")]
    elif loc == "ZNI":
        df = df[~df["TECHNOLOGY"].str.contains("RUR")]
        df = df[df["TECHNOLOGY"].str.contains("ZNI")]

    return df


def _asignar_categoria(
    df: pd.DataFrame,
    agrupacion: str,
) -> pd.DataFrame:
    """Crea columna CATEGORIA según el tipo de agrupación.

    Port de ``graficas_comparacion._asignar_categoria``.
    """
    df = df.copy()

    if agrupacion == "TECNOLOGIA":
        df["CATEGORIA"] = df["TECHNOLOGY"]

    elif agrupacion == "COMBUSTIBLE":
        if "FUEL" in df.columns:
            df["_TECH_FUEL"] = (
                df["TECHNOLOGY"].astype(str) + "_" + df["FUEL"].astype(str)
            )
        else:
            df["_TECH_FUEL"] = df["TECHNOLOGY"].astype(str)

        df["CATEGORIA"] = df["_TECH_FUEL"].apply(asignar_grupo)
        df = df.drop(columns="_TECH_FUEL")

    elif agrupacion == "SECTOR":
        df["CATEGORIA"] = df["TECHNOLOGY"].str[:6].map(MAPA_SECTOR)

    return df


def _convertir_unidades(df: pd.DataFrame, un: str) -> pd.DataFrame:
    """Convierte columna VALUE a las unidades solicitadas.

    Port de ``graficas_comparacion._convertir_unidades``.
    """
    df = df.copy()
    if un == "GW":
        df["VALUE"] /= 31.536
    elif un == "MW":
        df["VALUE"] /= 0.031536
    elif un == "TWh":
        df["VALUE"] /= 3.6
    elif un == "Gpc":
        df["VALUE"] /= 1.0095581216
    # PJ: unidad base, sin conversión
    return df


def _color_map_comparison(
    agrupacion: str,
    categorias_unicas: list[str],
) -> dict[str, str]:
    """Devuelve ``{categoria: color_hex}`` para gráficas de comparación.

    Port de ``graficas_comparacion._color_map``.
    """
    if agrupacion == "COMBUSTIBLE":
        return {c: COLORES_GRUPOS.get(c, "#999999") for c in categorias_unicas}

    if agrupacion == "SECTOR":
        return {c: COLORES_SECTOR.get(c, "#999999") for c in categorias_unicas}

    # TECNOLOGIA: reutiliza generar_colores_tecnologias de colors.py
    df_tmp = pd.DataFrame({"COLOR": list(categorias_unicas)})
    colores_lista, orden_lista = generar_colores_tecnologias(df_tmp, "COLOR")
    return dict(zip(orden_lista, colores_lista))


# ═══════════════════════════════════════════════════════════════════════════
# 3. build_chart_data — SINGLE ESCENARIO
# ═══════════════════════════════════════════════════════════════════════════

def build_chart_data(
    db: Session,
    job_id: int,
    tipo: str,
    un: str = "PJ",
    sub_filtro: str | None = None,
    loc: str | None = None,
    variable: str | None = None,
    agrupar_por: str | None = None,
) -> ChartDataResponse:
    """Construye la respuesta de gráfica para un solo escenario.

    Parámetros
    ----------
    db : Session
    job_id : int
    tipo : str
        Clave en ``CONFIGS`` (ej: ``'cap_electricidad'``, ``'gas_consumo'``).
    un : str
        Unidades de salida (PJ, GW, MW, TWh, Gpc).
    sub_filtro : str | None
        Filtro adicional dentro del sector.
    loc : str | None
        Localización (URB, RUR, ZNI).
    variable : str | None
        Override de variable para configs de capacidad.
    """
    if tipo not in CONFIGS:
        raise ValueError(f"tipo='{tipo}' no existe en CONFIGS.")

    cfg = CONFIGS[tipo]
    es_capacidad = cfg.get("es_capacidad", False)
    es_porcentaje = cfg.get("es_porcentaje", False)

    # Variable a consultar
    variable_name = variable if (variable and es_capacidad) else cfg["variable_default"]

    # ── Título ───────────────────────────────────────────────────────────
    if es_capacidad:
        titulo_var = TITULOS_VARIABLES_CAPACIDAD.get(variable_name, variable_name)
        title = f"{cfg['titulo_base']} — {titulo_var}"
    elif es_porcentaje:
        title = cfg.get("titulo_base", cfg.get("titulo", tipo))
    else:
        title = cfg.get("titulo", tipo)

    if sub_filtro:
        title += f" — {sub_filtro}"
    if loc:
        title += f" ({loc})"

    title += f" ({un})"

    # ── Cargar datos ─────────────────────────────────────────────────────
    df = _load_variable_data(db, job_id, variable_name)

    if df.empty:
        return ChartDataResponse(
            categories=[], series=[], title=title, yAxisLabel=un,
        )

    # ── Filtrar ──────────────────────────────────────────────────────────
    filtro_fn = cfg.get("filtro")
    if filtro_fn is not None:
        df = filtro_fn(df, sub_filtro=sub_filtro, loc=loc)

    if df.empty:
        return ChartDataResponse(
            categories=[], series=[], title=title, yAxisLabel=un,
        )

    # ── Agrupación ───────────────────────────────────────────────────────
    agrupar_col = agrupar_por if agrupar_por is not None else cfg["agrupar_por"]

    if agrupar_col == "TECNOLOGIA":
        df["COLOR"] = df["TECHNOLOGY"]
    elif agrupar_col == "GROUP":
        if "FUEL" in df.columns:
            df["COLOR"] = (
                df["TECHNOLOGY"] + "_" + df["FUEL"]
            ).apply(asignar_grupo)
        else:
            df["COLOR"] = df["TECHNOLOGY"].apply(asignar_grupo)
    elif agrupar_col == "FUEL":
        if "FUEL" in df.columns:
            df["COLOR"] = df["FUEL"].apply(asignar_grupo)
        else:
            df["COLOR"] = df["TECHNOLOGY"].apply(asignar_grupo)
    elif agrupar_col == "SECTOR":
        df["COLOR"] = df["TECHNOLOGY"].str[:6].map(MAPA_SECTOR)
    elif agrupar_col == "YEAR":
        # emisiones_total: solo agrupa por año
        df["COLOR"] = "Total"
    else:
        df["COLOR"] = df["TECHNOLOGY"]

    # ── Agregar ──────────────────────────────────────────────────────────
    df_agg = df.groupby(["COLOR", "YEAR"], as_index=False)["VALUE"].sum()

    # Descartar grupos insignificantes
    df_agg = df_agg[df_agg.groupby("COLOR")["VALUE"].transform("sum") > 1e-5]

    if df_agg.empty:
        return ChartDataResponse(
            categories=[], series=[], title=title, yAxisLabel=un,
        )

    # ── Conversión de unidades ───────────────────────────────────────────
    df_agg = _convertir_unidades(df_agg, un)

    # ── Porcentaje (prd_electricidad) ────────────────────────────────────
    if es_porcentaje:
        total_por_año = df_agg.groupby("YEAR")["VALUE"].transform("sum")
        df_agg["VALUE"] = df_agg["VALUE"] / total_por_año * 100.0

    # ── Colores ──────────────────────────────────────────────────────────
    # Si agrupar_por fue overridden, ajustar color_fn según agrupación
    if agrupar_por is not None and agrupar_por != cfg.get("agrupar_por"):
        if agrupar_col in ("FUEL", "GROUP"):
            color_fn = _color_por_grupo_fijo
        else:
            # TECNOLOGIA u otro: usar electricidad si el config lo usa, sino generar_colores
            color_fn = cfg.get("color_fn") if cfg.get("color_fn") == _color_electricidad else generar_colores_tecnologias
    else:
        color_fn = cfg.get("color_fn")
    if color_fn is not None:
        colores_ordenados, orden_color = color_fn(df_agg, "COLOR")
    else:
        orden_color = sorted(df_agg["COLOR"].unique())
        colores_ordenados = [COLORES_GRUPOS.get(c, "#999999") for c in orden_color]

    color_dict = dict(zip(orden_color, colores_ordenados))

    # ── Construir respuesta ──────────────────────────────────────────────
    años = sorted(df_agg["YEAR"].unique())
    categories = [str(a) for a in años]

    series: list[ChartSeries] = []
    for tech in orden_color:
        df_tech = df_agg[df_agg["COLOR"] == tech]
        valor_por_año = {int(row["YEAR"]): row["VALUE"] for _, row in df_tech.iterrows()}
        data = [round(valor_por_año.get(a, 0.0), 6) for a in años]
        series.append(
            ChartSeries(
                name=str(tech),
                data=data,
                color=color_dict.get(tech, "#999999"),
                stack="default",
            )
        )

    return ChartDataResponse(
        categories=categories,
        series=series,
        title=title,
        yAxisLabel="%" if es_porcentaje else un,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 4. build_comparison_data — MULTI-ESCENARIO
# ═══════════════════════════════════════════════════════════════════════════

def build_comparison_data(
    db: Session,
    job_ids: list[int],
    tipo: str,
    un: str = "PJ",
    years_to_plot: list[int] | None = None,
    agrupacion: str | None = None,
    sub_filtro: str | None = None,
    loc: str | None = None,
) -> CompareChartResponse:
    """Construye la respuesta de comparación multi-escenario.

    Genera subplots por año clave, con barras apiladas por categoría.

    Parámetros
    ----------
    db : Session
    job_ids : list[int]
        IDs de simulation_job a comparar (max 10).
    tipo : str
        Clave en ``CONFIGS_COMPARACION``.
    un : str
        Unidades.
    years_to_plot : list[int] | None
        Años clave (default: [2024, 2030, 2050]).
    agrupacion : str | None
        Override de agrupación (TECNOLOGIA, COMBUSTIBLE, SECTOR).
    sub_filtro, loc : str | None
        Filtros opcionales.
    """
    # MAPEO DE SECTORES A COMPARACIÓN (Si el usuario escoge la tabla normal, la mappeamos a su configuración de comparación)
    MAPEO_COMPARACION = {
        "tra_total": "tra_comparacion",
        "ind_total": "ind_comparacion",
        "res_total": "res_comparacion",
        "ter_total": "ter_comparacion",
    }
    
    es_generico = False
    if tipo in MAPEO_COMPARACION:
        tipo = MAPEO_COMPARACION[tipo]

    if tipo not in CONFIGS_COMPARACION:
        if tipo in CONFIGS:
            es_generico = True
            cfg = CONFIGS[tipo]
        else:
            raise ValueError(f"tipo='{tipo}' no existe ni en CONFIGS ni en CONFIGS_COMPARACION.")
    else:
        cfg = CONFIGS_COMPARACION[tipo]

    if years_to_plot is None:
        years_to_plot = [2024, 2030, 2050]

    # Resolver agrupación y año histórico
    if not es_generico:
        prefijo = cfg["prefijo"]
        agrupacion_fija = cfg.get("agrupacion_fija")
        if agrupacion_fija is not None:
            agrupacion_usar = agrupacion_fija
        elif agrupacion is not None:
            agrupacion_usar = agrupacion
        else:
            agrupacion_usar = cfg["agrupacion_default"]
            
        usa_historico = cfg["año_historico_unico"]
        año_historico = years_to_plot[0] if years_to_plot else 2024
        
        label_agrupacion = {
            "TECNOLOGIA": "Tecnologías",
            "COMBUSTIBLE": "Combustibles",
            "SECTOR": "Sectores",
        }.get(agrupacion_usar, agrupacion_usar)
        title_base = f"{cfg['titulo_base']} por {label_agrupacion}"
    else:
        usa_historico = False
        año_historico = years_to_plot[0] if years_to_plot else 2024
        agrupacion_usar = "TECNOLOGIA" # Fallback a agrupar por tecnología para cualquier otra gráfica
        title_base = cfg.get("titulo", cfg.get("titulo_base", tipo)) + " (Comparación)"

    title = title_base
    if sub_filtro:
        title += f" — {sub_filtro}"
    if loc:
        title += f" ({loc})"
    title += f" ({un})"

    # ── Cargar nombres de escenarios ─────────────────────────────────────
    scenario_names: dict[int, str] = {}
    for jid in job_ids:
        job = db.query(SimulationJob).filter(SimulationJob.id == jid).first()
        if job:
            # Usar el nombre del escenario si está disponible
            from app.models import Scenario
            scenario = db.query(Scenario).filter(Scenario.id == job.scenario_id).first()
            scenario_names[jid] = scenario.name if scenario else f"Job {jid}"
        else:
            scenario_names[jid] = f"Job {jid}"

    variable_name = cfg["variable_default"]

    # ── Procesar datos ───────────────────────────────────────────────────
    all_data: list[pd.DataFrame] = []

    # Paso 1: Año histórico (solo del primer escenario)
    if usa_historico and año_historico in years_to_plot and job_ids:
        first_job_id = job_ids[0]
        df_var = _load_variable_data(db, first_job_id, variable_name)

        if not df_var.empty:
            df_hist = _procesar_bloque_comparacion(
                df_var, prefijo, sub_filtro, loc,
                agrupacion_usar, [año_historico], un,
            )
            if df_hist is not None and not df_hist.empty:
                df_hist["SCENARIO"] = str(año_historico)
                all_data.append(df_hist)

    # Paso 2: Años proyectados (todos los escenarios)
    años_a_procesar = (
        [y for y in years_to_plot if y != año_historico]
        if usa_historico
        else years_to_plot
    )

    for jid in job_ids:
        df_var = _load_variable_data(db, jid, variable_name)
        if df_var.empty:
            continue

        if not es_generico:
            df = _procesar_bloque_comparacion(
                df_var, prefijo, sub_filtro, loc,
                agrupacion_usar, años_a_procesar, un,
            )
        else:
            df = _procesar_bloque_single(
                df_var, cfg, sub_filtro, loc, años_a_procesar, un
            )

        if df is None or df.empty:
            continue

        df["SCENARIO"] = scenario_names.get(jid, f"Job {jid}")
        all_data.append(df)

    if not all_data:
        return CompareChartResponse(title=title, subplots=[], yAxisLabel=un)

    df_final = pd.concat(all_data, ignore_index=True)

    # ── Colores ──────────────────────────────────────────────────────────
    categorias_unicas = sorted(df_final["CATEGORIA"].dropna().unique())
    if not es_generico:
        mapa_colores = _color_map_comparison(agrupacion_usar, categorias_unicas)
    else:
        # Reutilizar el sistema de colores original de la gráfica base
        color_fn = cfg.get("color_fn")
        if color_fn is not None:
            # Fake dataframe for generic coloring
            df_tmp = pd.DataFrame({"COLOR": list(categorias_unicas)})
            colores_lista, orden_lista = color_fn(df_tmp, "COLOR")
            mapa_colores = dict(zip(orden_lista, colores_lista))
        else:
            mapa_colores = {c: COLORES_GRUPOS.get(c, "#999999") for c in categorias_unicas}

    # ── Construir subplots por año ───────────────────────────────────────
    años_ordenados = sorted(df_final["YEAR"].unique())
    subplots: list[SubplotData] = []

    for año in años_ordenados:
        df_año = df_final[df_final["YEAR"] == año]
        escenarios_en_año = sorted(df_año["SCENARIO"].unique())

        series: list[ChartSeries] = []
        for categoria in categorias_unicas:
            df_cat = df_año[df_año["CATEGORIA"] == categoria]
            if df_cat.empty:
                continue

            valor_por_escenario = {
                row["SCENARIO"]: row["VALUE"]
                for _, row in df_cat.groupby("SCENARIO", as_index=False)["VALUE"].sum().iterrows()
            }
            data = [round(valor_por_escenario.get(esc, 0.0), 6) for esc in escenarios_en_año]

            series.append(
                ChartSeries(
                    name=str(categoria),
                    data=data,
                    color=mapa_colores.get(categoria, "#999999"),
                    stack="default",
                )
            )

        subplots.append(
            SubplotData(
                year=int(año),
                categories=escenarios_en_año,
                series=series,
            )
        )

    return CompareChartResponse(title=title, subplots=subplots, yAxisLabel=un)


# ═══════════════════════════════════════════════════════════════════════════
# 4b. build_comparison_facet_data — ESCENARIOS COMPLETOS (FACETS)
# ═══════════════════════════════════════════════════════════════════════════

def build_comparison_facet_data(
    db: Session,
    job_ids: list[int],
    tipo: str,
    un: str = "PJ",
    sub_filtro: str | None = None,
    loc: str | None = None,
    variable: str | None = None,
    agrupar_por: str | None = None,
) -> CompareChartFacetResponse:
    """Construye datos para comparación por escenarios completos (facets).

    Cada facet muestra la evolución temporal completa de un escenario.
    Usa CONFIGS (no CONFIGS_COMPARACION). Una query por job_id.

    Parámetros
    ----------
    db : Session
    job_ids : list[int]
        IDs de simulation_job a comparar (max 10).
    tipo : str
        Clave en CONFIGS (ej: 'cap_electricidad', 'gas_consumo').
    un : str
        Unidades de salida (PJ, GW, etc.).
    sub_filtro, loc, variable : str | None
        Filtros y override de variable.
    """
    if tipo not in CONFIGS:
        raise ValueError(f"tipo='{tipo}' no encontrado en CONFIGS.")

    cfg = CONFIGS[tipo]
    title_base = cfg.get("titulo", cfg.get("titulo_base", tipo))
    title = title_base
    if sub_filtro:
        title += f" — {sub_filtro}"
    if loc:
        title += f" ({loc})"
    title += f" ({un})"

    facets: list[FacetData] = []
    y_label = un
    from app.models import Scenario

    for jid in job_ids:
        job = db.query(SimulationJob).filter(SimulationJob.id == jid).first()
        if not job:
            continue
        scenario = db.query(Scenario).filter(Scenario.id == job.scenario_id).first()
        scenario_name = scenario.name if scenario else f"Job {jid}"

        chart = build_chart_data(
            db=db,
            job_id=jid,
            tipo=tipo,
            un=un,
            sub_filtro=sub_filtro,
            loc=loc,
            variable=variable,
            agrupar_por=agrupar_por,
        )

        if not facets:
            y_label = chart.yAxisLabel
        facets.append(
            FacetData(
                scenario_name=scenario_name,
                job_id=jid,
                categories=chart.categories,
                series=chart.series,
            )
        )
    return CompareChartFacetResponse(
        title=title,
        facets=facets,
        yAxisLabel=y_label,
    )


def _procesar_bloque_comparacion(
    df_var: pd.DataFrame,
    prefijo: str | tuple[str, ...],
    sub_filtro: str | None,
    loc: str | None,
    agrupacion: str,
    años: list[int],
    un: str,
) -> pd.DataFrame | None:
    """Pipeline para un bloque de datos de comparación.

    filtrar → filtrar años → asignar categorías → agregar → convertir.
    Port de ``graficas_comparacion._procesar_bloque``.
    """
    if df_var is None or df_var.empty:
        return None

    if "TECHNOLOGY" not in df_var.columns or "YEAR" not in df_var.columns:
        return None

    df = _filtrar_df(df_var, prefijo, sub_filtro, loc)
    if df.empty:
        return None

    df = df[df["YEAR"].isin(años)]
    if df.empty:
        return None

    df = _asignar_categoria(df, agrupacion)

    df = df.groupby(["CATEGORIA", "YEAR"], as_index=False)["VALUE"].sum()

    # Descartar categorías insignificantes
    df = df[df.groupby("CATEGORIA")["VALUE"].transform("sum") > 1e-5]
    if df.empty:
        return None

    df = _convertir_unidades(df, un)

    return df


def _procesar_bloque_single(
    df_var: pd.DataFrame,
    cfg: dict,
    sub_filtro: str | None,
    loc: str | None,
    años: list[int],
    un: str,
) -> pd.DataFrame | None:
    """Procesador genérico que emula la agrupación de build_chart_data para comparación."""
    if df_var is None or df_var.empty:
        return None

    if "TECHNOLOGY" not in df_var.columns or "YEAR" not in df_var.columns:
        return None
        
    df = df_var.copy()
    
    filtro_fn = cfg.get("filtro")
    if filtro_fn is not None:
        df = filtro_fn(df, sub_filtro=sub_filtro, loc=loc)
        
    if df.empty:
        return None
        
    df = df[df["YEAR"].isin(años)]
    if df.empty:
        return None
        
    agrupar_col = cfg["agrupar_por"]
    
    if agrupar_col == "TECNOLOGIA":
        df["CATEGORIA"] = df["TECHNOLOGY"]
    elif agrupar_col == "GROUP":
        if "FUEL" in df.columns:
            df["CATEGORIA"] = (df["TECHNOLOGY"] + "_" + df["FUEL"]).apply(asignar_grupo)
        else:
            df["CATEGORIA"] = df["TECHNOLOGY"].apply(asignar_grupo)
    elif agrupar_col == "FUEL":
        if "FUEL" in df.columns:
            df["CATEGORIA"] = df["FUEL"].apply(asignar_grupo)
        else:
            df["CATEGORIA"] = df["TECHNOLOGY"].apply(asignar_grupo)
    elif agrupar_col == "SECTOR":
        df["CATEGORIA"] = df["TECHNOLOGY"].str[:6].map(MAPA_SECTOR)
    elif agrupar_col == "YEAR":
        df["CATEGORIA"] = "Total"
    else:
        df["CATEGORIA"] = df["TECHNOLOGY"]
        
    df = df.groupby(["CATEGORIA", "YEAR"], as_index=False)["VALUE"].sum()
    df = df[df.groupby("CATEGORIA")["VALUE"].transform("sum") > 1e-5]
    
    if df.empty:
        return None
        
    df = _convertir_unidades(df, un)
    return df



# ═══════════════════════════════════════════════════════════════════════════
# 5. get_result_summary — KPIs
# ═══════════════════════════════════════════════════════════════════════════

def get_result_summary(
    db: Session,
    job_id: int,
) -> ResultSummaryResponse:
    """Devuelve resumen de KPIs para el header de visualización."""
    job = db.query(SimulationJob).filter(SimulationJob.id == job_id).first()

    if not job:
        raise ValueError(f"Job {job_id} no encontrado.")

    # Obtener nombre del escenario
    from app.models import Scenario

    scenario = db.query(Scenario).filter(Scenario.id == job.scenario_id).first()
    scenario_name = scenario.name if scenario else None

    solver_status = (job.model_timings_json or {}).get("solver_status", "unknown")

    # Total CO2 emissions
    total_co2 = (
        db.query(func.coalesce(func.sum(OsemosysOutputParamValue.value), 0))
        .filter(
            OsemosysOutputParamValue.id_simulation_job == job_id,
            OsemosysOutputParamValue.variable_name == "AnnualEmissions",
        )
        .scalar()
    ) or 0.0

    return ResultSummaryResponse(
        job_id=job.id,
        scenario_id=job.scenario_id,
        scenario_name=scenario_name,
        solver_name=job.solver_name,
        solver_status=solver_status,
        objective_value=job.objective_value or 0.0,
        coverage_ratio=job.coverage_ratio or 0.0,
        total_demand=job.total_demand or 0.0,
        total_dispatch=job.total_dispatch or 0.0,
        total_unmet=job.total_unmet or 0.0,
        total_co2=float(total_co2),
    )


# ═══════════════════════════════════════════════════════════════════════════
# 6. get_chart_catalog — CATÁLOGO DE GRÁFICAS
# ═══════════════════════════════════════════════════════════════════════════

def get_chart_catalog() -> list[ChartCatalogItem]:
    """Devuelve la lista de gráficas disponibles para el selector del frontend."""
    items: list[ChartCatalogItem] = []

    for config_id, cfg in CONFIGS.items():
        label = cfg.get("titulo", cfg.get("titulo_base", config_id))
        items.append(
            ChartCatalogItem(
                id=config_id,
                label=label,
                variable_default=cfg["variable_default"],
                has_sub_filtro=_config_has_sub_filtro(cfg),
                has_loc=_config_has_loc(cfg),
                sub_filtros=_config_sub_filtros(cfg),
                es_capacidad=cfg.get("es_capacidad", False),
            )
        )

    return items


def _config_has_sub_filtro(cfg: dict) -> bool:
    """Determina si un config single-scenario soporta sub_filtro.

    Los configs de residencial, industrial, transporte y terciario
    aceptan sub_filtro a través de su función filtro.
    """
    filtro = cfg.get("filtro")
    if filtro is None:
        return False
    # Funciones que soportan sub_filtro por su signature
    filtro_name = getattr(filtro, "__name__", "")
    return filtro_name in (
        "_filtro_residencial",
        "_filtro_industrial",
        "_filtro_transporte",
        "_filtro_terciario",
        "_filtro_prefijo_con_sub",
        "_filtro_construccion",
        "_filtro_agroforestal",
        "_filtro_mineria",
        "_filtro_coquerias",
    )


def _config_has_loc(cfg: dict) -> bool:
    """Determina si un config single-scenario soporta localización."""
    filtro = cfg.get("filtro")
    if filtro is None:
        return False
    filtro_name = getattr(filtro, "__name__", "")
    return filtro_name == "_filtro_residencial"


def _config_sub_filtros(cfg: dict) -> list[str] | None:
    """Devuelve la lista de sub_filtros conocidos para un config, o None."""
    filtro = cfg.get("filtro")
    if filtro is None:
        return None
    filtro_name = getattr(filtro, "__name__", "")
    if filtro_name == "_filtro_residencial":
        return ["CKN", "WHT", "AIR", "REF", "ILU", "TV", "OTH"]
    if filtro_name == "_filtro_industrial":
        return ["BOI", "FUR", "MPW", "AIR", "REF", "ILU", "OTH"]
    if filtro_name == "_filtro_transporte":
        return ["AVI", "BOT", "SHP", "LDV", "FWD", "BUS", "TCK_C2P", "TCK_CSG", "MOT", "MIC", "TAX", "STT", "MET"]
    if filtro_name == "_filtro_terciario":
        return ["AIR", "ILU", "OTH"]
    return None


# ═══════════════════════════════════════════════════════════════════════════
# 7. EXPORT ALL — ZIP con gráficas como imágenes
# ═══════════════════════════════════════════════════════════════════════════

def export_all_charts_zip(
    db: Session,
    job_id: int,
    un: str = "PJ",
    fmt: str = "svg",
) -> "io.BytesIO":
    """Genera un ZIP con todas las gráficas renderizadas como SVG o PNG.

    Para configs de capacidad genera 3 figuras (Total, Nueva, Acumulada).
    Retorna un BytesIO listo para streaming.
    """
    import io
    import zipfile

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker

    CAPACITY_VARIABLES = [
        ("TotalCapacityAnnual", "Cap_Total"),
        ("NewCapacity", "Cap_Nueva"),
        ("AccumulatedNewCapacity", "Cap_Acumulada"),
    ]

    ext = "svg" if fmt == "svg" else "png"
    output = io.BytesIO()

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        file_count = 0

        for config_id, cfg in CONFIGS.items():
            es_capacidad = cfg.get("es_capacidad", False)
            label = cfg.get("titulo", cfg.get("titulo_base", config_id))

            charts_to_render: list[tuple[str, ChartDataResponse]] = []

            if es_capacidad:
                for var_name, var_suffix in CAPACITY_VARIABLES:
                    chart = build_chart_data(
                        db, job_id, config_id, un=un, variable=var_name,
                    )
                    if chart.series:
                        charts_to_render.append(
                            (f"{label} — {var_suffix}", chart)
                        )
            else:
                chart = build_chart_data(db, job_id, config_id, un=un)
                if chart.series:
                    charts_to_render.append((label, chart))

            for chart_label, chart_data in charts_to_render:
                img_buf = _render_stacked_bar(
                    chart_data, chart_label, fmt=ext,
                )
                safe_name = _safe_filename(chart_label)
                zf.writestr(f"{safe_name}.{ext}", img_buf.getvalue())
                file_count += 1

    output.seek(0)
    return output


def _render_stacked_bar(
    chart: ChartDataResponse,
    title: str,
    fmt: str = "svg",
) -> "io.BytesIO":
    """Renderiza un ChartDataResponse como gráfica de barras apiladas con matplotlib."""
    import io
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    categories = chart.categories
    n_cats = len(categories)
    x = np.arange(n_cats)

    fig, ax = plt.subplots(figsize=(max(12, n_cats * 0.5), 7))

    bottom = np.zeros(n_cats)

    for s in chart.series:
        values = np.array(s.data, dtype=float)
        ax.bar(x, values, bottom=bottom, label=s.name, color=s.color, width=0.7)
        bottom += values

    # Stack totals on top
    for i, total in enumerate(bottom):
        if total > 0:
            ax.text(
                i, total, f"{total:,.1f}",
                ha="center", va="bottom", fontsize=7, color="#333",
            )

    ax.set_xticks(x)
    ax.set_xticklabels(categories, rotation=45 if n_cats > 15 else 0, ha="right" if n_cats > 15 else "center", fontsize=8)
    ax.set_ylabel(chart.yAxisLabel, fontsize=10)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.legend(
        loc="upper center", bbox_to_anchor=(0.5, -0.15),
        ncol=min(len(chart.series), 5), fontsize=7, frameon=False,
    )
    ax.grid(axis="y", alpha=0.3, linewidth=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _safe_filename(name: str) -> str:
    """Genera un nombre de archivo seguro."""
    clean = "".join(c if c.isalnum() or c in (" ", "_", "-") else "_" for c in name)
    return clean.strip()[:80]


# ═══════════════════════════════════════════════════════════════════════════
# 8. EXPORT RAW DATA — Excel
# ═══════════════════════════════════════════════════════════════════════════

def export_raw_data_excel(
    db: Session,
    job_id: int,
) -> "io.BytesIO":
    """Exporta todos los datos crudos del job a un archivo Excel (.xlsx)."""
    import io
    
    rows = (
        db.query(OsemosysOutputParamValue)
        .filter(OsemosysOutputParamValue.id_simulation_job == job_id)
        .all()
    )
    
    if not rows:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail="No hay datos crudos disponibles para este escenario. La simulación puede no haber guardado resultados en la base de datos.",
        )
        
    records = []
    for r in rows:
        records.append({
            "VariableName": r.variable_name,
            "Technology": r.technology_name or "",
            "Fuel": r.fuel_name or "",
            "Emission": r.emission_name or "",
            "Year": r.year,
            "Value": float(r.value),
            "IndexJSON": str(r.index_json) if r.index_json else "",
        })
        
    df = pd.DataFrame(records)
    
    output = io.BytesIO()
    from openpyxl.utils import get_column_letter

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Raw Data', index=False)
        worksheet = writer.sheets['Raw Data']
        # Autofit columns without depending on xlsxwriter.
        for idx, col in enumerate(df):
            series = df[col]
            max_len = max((
                series.astype(str).map(len).max(),
                len(str(series.name))
            )) + 2
            worksheet.column_dimensions[get_column_letter(idx + 1)].width = max_len
            
    output.seek(0)
    return output
