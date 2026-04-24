"""Seed inicial del catálogo editable de visualización (Fase 3.1).

Lee los dicts hardcodeados en:
  - app/visualization/configs.py (CONFIGS, DATA_EXPLORER_FILTERS,
    TITULOS_VARIABLES_CAPACIDAD, NOMBRES_COMBUSTIBLES)
  - app/visualization/configs_comparacion.py (MAPA_SECTOR, COLORES_SECTOR)
  - app/visualization/colors.py (FAMILIAS_TEC, COLORES_GRUPOS,
    COLOR_MAP_PWR, COLORES_EMISIONES, COLOR_BASE_FAMILIA)
  - app/visualization/labels.py (DISPLAY_NAMES)

Adicionalmente contiene el espejo en Python de la jerarquía MENU del
``frontend/src/shared/charts/ChartSelector.tsx`` para poblar los módulos,
submódulos y metadata por chart (allowedGroupings, defaultGrouping,
subFiltros, soportaPareto, hasLoc, subFiltroLabel).

Idempotente: usa ``INSERT ... ON CONFLICT DO UPDATE`` para reejecución segura.

Uso dentro del contenedor api:

    docker compose exec api python scripts/seed_visualization_catalog.py
    docker compose exec api python scripts/seed_visualization_catalog.py --dry-run
    docker compose exec api python scripts/seed_visualization_catalog.py --section colors
    docker compose exec api python scripts/seed_visualization_catalog.py --section all
"""

from __future__ import annotations

import argparse
import logging
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    CatalogMetaChartConfig,
    CatalogMetaChartModule,
    CatalogMetaChartSubfilter,
    CatalogMetaChartSubmodule,
    CatalogMetaColorPalette,
    CatalogMetaLabel,
    CatalogMetaSectorMapping,
    CatalogMetaTechFamily,
    CatalogMetaVariableUnit,
)
from app.visualization.colors import (
    COLOR_BASE_FAMILIA,
    COLOR_MAP_PWR,
    COLORES_EMISIONES,
    COLORES_GRUPOS,
    FAMILIAS_TEC,
)
from app.visualization.configs import (
    CONFIGS,
    DATA_EXPLORER_FILTERS,
    NOMBRES_COMBUSTIBLES,
    TITULOS_VARIABLES_CAPACIDAD,
)
from app.visualization.configs_comparacion import COLORES_SECTOR, MAPA_SECTOR
from app.visualization.labels import DISPLAY_NAMES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("seed")


# ---------------------------------------------------------------------------
#  Espejo Python del MENU de ChartSelector.tsx
# ---------------------------------------------------------------------------
# Estructura: {module_code: {label, icon, sort_order, subsectors?, charts?}}
# Cada chart: {tipo, label, allowed_groupings?, default_grouping?,
#   sub_filtros?, sub_filtro_label?, has_loc?, is_capacity?, soporta_pareto?}

_TRA_SUBFILTROS = [
    "CARRETERA", "AVI", "BOT", "SHP",
    "LDV", "FWD", "BUS", "TCK_C2P", "TCK_CSG", "MOT", "MIC", "TAX", "STT", "MET",
]
_RES_SUBFILTROS = ["CKN", "WHT", "AIR", "REF", "ILU", "TV", "OTH"]
_IND_SUBFILTROS = ["BOI", "FUR", "MPW", "AIR", "REF", "ILU", "OTH"]
_TER_SUBFILTROS = ["AIR", "ILU", "OTH"]
_DEM_CONSUMO_COMBUSTIBLES = [
    "NGS", "DSL", "ELC", "GSL", "COA", "LPG", "WOO", "BGS", "BAG", "HDG", "FOL",
    "BDL", "JET", "WAS", "OIL", "AFR", "SAF",
]

MENU: list[dict[str, Any]] = [
    {
        "code": "electrico", "label": "Sector Eléctrico", "icon": "⚡",
        "charts": [
            {"tipo": "elec_produccion",  "label": "Producción de Electricidad - ProductionByTechnology", "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
            {"tipo": "prd_electricidad", "label": "Producción de Electricidad - ProductionByTechnology (%)"},
            {"tipo": "cap_electricidad", "label": "Matriz Eléctrica (Capacidad) - TotalCapacityAnnual", "is_capacity": True},
            {"tipo": "factor_planta",    "label": "Factor de Planta (%)"},
        ],
    },
    {
        "code": "demanda", "label": "Demanda Final — Sectores", "icon": "🏠",
        "subsectors": [
            {"code": "consum_combustible", "label": "🔥 Todos los Sectores",
             "charts": [
                 {"tipo": "dem_consumo_combustible", "label": "Consumo Por Sector",
                  "sub_filtro_label": "Combustible", "sub_filtros": _DEM_CONSUMO_COMBUSTIBLES,
                  "allowed_groupings": ["SECTOR", "FUEL"], "default_grouping": "SECTOR"},
             ]},
            {"code": "residencial", "label": "🏘️ Residencial",
             "charts": [
                 {"tipo": "res_total", "label": "Sector Residencial - Consumo Total - UseByTechnology",
                  "sub_filtro_label": "Uso", "has_loc": True, "sub_filtros": _RES_SUBFILTROS,
                  "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
                 {"tipo": "res_uso", "label": "Sector Residencial - ProductionByTechnology",
                  "sub_filtro_label": "Uso", "has_loc": True, "sub_filtros": _RES_SUBFILTROS,
                  "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
             ]},
            {"code": "industrial", "label": "🏗️ Industrial",
             "charts": [
                 {"tipo": "ind_total", "label": "Sector Industrial - Consumo Total - UseByTechnology",
                  "sub_filtro_label": "Uso", "sub_filtros": _IND_SUBFILTROS,
                  "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
                 {"tipo": "ind_uso", "label": "Sector Industrial - ProductionByTechnology",
                  "sub_filtro_label": "Uso", "sub_filtros": _IND_SUBFILTROS,
                  "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
             ]},
            {"code": "transporte", "label": "🚗 Transporte",
             "charts": [
                 {"tipo": "tra_total", "label": "Sector Transporte - Consumo Total - UseByTechnology",
                  "sub_filtro_label": "Modo", "sub_filtros": _TRA_SUBFILTROS,
                  "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
                 {"tipo": "tra_uso", "label": "Sector Transporte - ProductionByTechnology",
                  "sub_filtro_label": "Modo", "sub_filtros": _TRA_SUBFILTROS,
                  "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
             ]},
            {"code": "terciario", "label": "🏢 Terciario",
             "charts": [
                 {"tipo": "ter_total", "label": "Sector Terciario - Consumo Total - UseByTechnology",
                  "sub_filtro_label": "Uso", "sub_filtros": _TER_SUBFILTROS,
                  "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
                 {"tipo": "ter_uso", "label": "Sector Terciario - ProductionByTechnology",
                  "sub_filtro_label": "Uso", "sub_filtros": _TER_SUBFILTROS,
                  "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
             ]},
            {"code": "construccion", "label": "🔨 Construcción",
             "charts": [{"tipo": "con_total", "label": "Sector Construcción - Consumo Total - UseByTechnology",
                         "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True}]},
            {"code": "agroforestal", "label": "🌾 Agroforestal",
             "charts": [{"tipo": "agf_total", "label": "Sector Agroforestal - Consumo Total - UseByTechnology",
                         "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True}]},
            {"code": "mineria_dem", "label": "⛏️ Minería (demanda)",
             "charts": [{"tipo": "min_total", "label": "Sector Minería - Consumo Total - UseByTechnology",
                         "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True}]},
            {"code": "coquerias", "label": "🧱 Coquerías",
             "charts": [{"tipo": "coq_total", "label": "Sector Coquerías - Consumo Total - UseByTechnology",
                         "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True}]},
            {"code": "otros_dem", "label": "📦 Otros Sectores",
             "charts": [{"tipo": "otros_total", "label": "Otros Sectores - Consumo Total - UseByTechnology",
                         "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True}]},
        ],
    },
    {
        "code": "capacidades", "label": "Capacidades Instaladas", "icon": "🏭",
        "charts": [
            {"tipo": "cap_industrial", "label": "Sector Industrial (Capacidad) - TotalCapacityAnnual", "is_capacity": True},
            {"tipo": "cap_transporte", "label": "Sector Transporte (Capacidad) - TotalCapacityAnnual", "is_capacity": True},
            {"tipo": "cap_terciario",  "label": "Sector Terciario (Capacidad) - TotalCapacityAnnual",  "is_capacity": True},
            {"tipo": "cap_otros",      "label": "Otros Sectores (Capacidad) - TotalCapacityAnnual",    "is_capacity": True},
            {"tipo": "ref_capacidad",  "label": "Capacidad de Refinación por Derivado",                "is_capacity": True},
        ],
    },
    {
        "code": "upstream", "label": "Upstream & Refinación", "icon": "🛢️",
        "charts": [
            {"tipo": "gas_consumo",    "label": "Gas Natural - UseByTechnology",                 "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
            {"tipo": "gas_produccion", "label": "Gas Natural - ProductionByTechnology",          "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
            {"tipo": "ref_total",      "label": "Refinerías - ProductionByTechnology",           "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
            {"tipo": "ref_consumo",    "label": "Refinerías — Consumo Total por Tecnología",     "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
            {"tipo": "ref_import",     "label": "Refinerías - Importaciones - ProductionByTechnology", "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
            {"tipo": "ref_cartagena",  "label": "Refinería de Cartagena - UseByTechnology",       "allowed_groupings": ["FUEL"], "soporta_pareto": True},
            {"tipo": "ref_barrancabermeja", "label": "Refinería de Barrancabermeja - UseByTechnology", "allowed_groupings": ["FUEL"], "soporta_pareto": True},
            {"tipo": "liquidos_prod_import", "label": "Líquidos - Producción + Importación",     "allowed_groupings": ["TECNOLOGIA", "FUEL"]},
            {"tipo": "ups_refinacion", "label": "Upstream Refinación - ProductionByTechnology",  "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
            {"tipo": "saf_produccion", "label": "SAF - Producción - ProductionByTechnology",     "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
        ],
    },
    {
        "code": "mineria", "label": "Minería & Extracción", "icon": "⛏️",
        "charts": [
            {"tipo": "min_hidrocarburos",  "label": "Minería Hidrocarburos - ProductionByTechnology", "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
            {"tipo": "min_carbon",         "label": "Minería Carbón - ProductionByTechnology",         "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
            {"tipo": "extraccion_min",     "label": "Minería - Extracción - ProductionByTechnology",    "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
            {"tipo": "solidos_extraccion", "label": "Sólidos - Extracción - ProductionByTechnology",    "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
            {"tipo": "solidos_import",     "label": "Sólidos - Importación - ProductionByTechnology",   "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
            {"tipo": "solidos_flujos",     "label": "Sólidos - Importación/Exportación - ProductionByTechnology", "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
        ],
    },
    {
        "code": "hidrogeno", "label": "Hidrógeno", "icon": "💧",
        "charts": [
            {"tipo": "cap_h2",     "label": "Hidrógeno - ProductionByTechnology",   "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
            {"tipo": "h2_consumo", "label": "Hidrógeno - Consumo - UseByTechnology", "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True},
        ],
    },
    {
        "code": "comercio", "label": "Comercio Exterior", "icon": "🚢",
        "charts": [{"tipo": "exp_liquidos_gas", "label": "Exportaciones — Líquidos y Gas", "allowed_groupings": ["TECNOLOGIA", "FUEL"], "soporta_pareto": True}],
    },
    {
        "code": "emisiones", "label": "Emisiones", "icon": "🌿",
        "charts": [
            {"tipo": "emisiones_total",        "label": "Emisiones - Total Anual - AnnualEmissions"},
            {"tipo": "emisiones_sectorial",    "label": "Emisiones - Por Sector - AnnualTechnologyEmission"},
            {"tipo": "emisiones_gei",          "label": "Emisiones GEI por Sector (CO₂, CH₄, N₂O)"},
            {"tipo": "emisiones_contaminantes", "label": "Emisiones Contaminantes Criterio (BC, CO, COV, NH₃, NOₓ, PM10, PM2.5, SOₓ)"},
            {"tipo": "emisiones_contaminantes_pct", "label": "Emisiones Contaminantes Criterio (%)"},
        ],
    },
    {
        "code": "otros", "label": "Otros", "icon": "♻️",
        "charts": [
            {"tipo": "oferta_bioenergia", "label": "Oferta Bioenergía - ProductionByTechnology", "allowed_groupings": ["TECNOLOGIA", "FUEL"]},
        ],
    },
]


# ---------------------------------------------------------------------------
#  Helpers upsert
# ---------------------------------------------------------------------------

def _upsert(db: Session, model, rows: list[dict], conflict_cols: list[str], update_cols: list[str]) -> int:
    """Insert rows with ON CONFLICT DO UPDATE. Retorna filas afectadas."""
    if not rows:
        return 0
    stmt = pg_insert(model).values(rows)
    update_map = {c: getattr(stmt.excluded, c) for c in update_cols}
    stmt = stmt.on_conflict_do_update(index_elements=conflict_cols, set_=update_map)
    db.execute(stmt)
    return len(rows)


# ---------------------------------------------------------------------------
#  Secciones de seed
# ---------------------------------------------------------------------------

def seed_colors(db: Session) -> dict[str, int]:
    rows: list[dict] = []
    # fuel — COLORES_GRUPOS (contiene algunas mezclas con DEMCON/DEMAGF/... que
    # técnicamente son sector, pero en el código se tratan como grupo tal cual).
    for i, (k, v) in enumerate(COLORES_GRUPOS.items()):
        rows.append({"group": "fuel", "key": k, "color_hex": v, "sort_order": i})
    # pwr — COLOR_MAP_PWR (derivado de FAMILIAS_TEC + COLOR_BASE_FAMILIA)
    for i, (k, v) in enumerate(COLOR_MAP_PWR.items()):
        rows.append({"group": "pwr", "key": k, "color_hex": v, "sort_order": i})
    # sector — COLORES_SECTOR
    for i, (k, v) in enumerate(COLORES_SECTOR.items()):
        rows.append({"group": "sector", "key": k, "color_hex": v, "sort_order": i})
    # emission — COLORES_EMISIONES
    for i, (k, v) in enumerate(COLORES_EMISIONES.items()):
        rows.append({"group": "emission", "key": k, "color_hex": v, "sort_order": i})
    # family base colors
    for i, (k, v) in enumerate(COLOR_BASE_FAMILIA.items()):
        rows.append({"group": "family", "key": k, "color_hex": v, "sort_order": i})
    n = _upsert(
        db, CatalogMetaColorPalette, rows,
        conflict_cols=["group", "key"],
        update_cols=["color_hex", "sort_order"],
    )
    return {"colors": n}


def seed_labels(db: Session) -> dict[str, int]:
    rows: list[dict] = []
    for i, (code, label) in enumerate(DISPLAY_NAMES.items()):
        rows.append({"code": code, "label_es": label, "category": "technology", "sort_order": i})
    # NOMBRES_COMBUSTIBLES: categoría "fuel" (puede sobrescribir a tech si hay choque).
    for i, (code, label) in enumerate(NOMBRES_COMBUSTIBLES.items()):
        rows.append({"code": f"FUEL::{code}", "label_es": label, "category": "fuel", "sort_order": i})
    # TITULOS_VARIABLES_CAPACIDAD
    for i, (code, label) in enumerate(TITULOS_VARIABLES_CAPACIDAD.items()):
        rows.append({"code": f"VAR_CAP::{code}", "label_es": label, "category": "var_capacidad", "sort_order": i})
    n = _upsert(
        db, CatalogMetaLabel, rows,
        conflict_cols=["code"],
        update_cols=["label_es", "category", "sort_order"],
    )
    return {"labels": n}


def seed_sectors(db: Session) -> dict[str, int]:
    rows = [
        {"tech_prefix": pref, "sector_name": sec, "sort_order": i}
        for i, (pref, sec) in enumerate(MAPA_SECTOR.items())
    ]
    n = _upsert(
        db, CatalogMetaSectorMapping, rows,
        conflict_cols=["tech_prefix"],
        update_cols=["sector_name", "sort_order"],
    )
    return {"sectors": n}


def seed_tech_families(db: Session) -> dict[str, int]:
    rows: list[dict] = []
    for family, prefixes in FAMILIAS_TEC.items():
        for i, pref in enumerate(prefixes):
            rows.append({"family_code": family, "tech_prefix": pref, "sort_order": i})
    n = _upsert(
        db, CatalogMetaTechFamily, rows,
        conflict_cols=["family_code", "tech_prefix"],
        update_cols=["sort_order"],
    )
    return {"tech_families": n}


def seed_modules_and_charts(db: Session) -> dict[str, int]:
    """Carga módulos, submódulos, charts, y sub-filtros."""
    counts = {"modules": 0, "submodules": 0, "charts": 0, "subfilters": 0}

    # 1. Módulos (upsert por code).
    module_rows = [
        {"code": m["code"], "label": m["label"], "icon": m.get("icon"), "sort_order": i}
        for i, m in enumerate(MENU)
    ]
    counts["modules"] = _upsert(
        db, CatalogMetaChartModule, module_rows,
        conflict_cols=["code"],
        update_cols=["label", "icon", "sort_order"],
    )
    db.flush()
    # Cargar ids
    module_id_by_code = dict(
        db.execute(select(CatalogMetaChartModule.code, CatalogMetaChartModule.id)).all()
    )

    # 2. Submódulos.
    submodule_rows: list[dict] = []
    for m in MENU:
        if not m.get("subsectors"):
            continue
        mod_id = module_id_by_code[m["code"]]
        for i, sub in enumerate(m["subsectors"]):
            submodule_rows.append({
                "module_id": mod_id,
                "code": sub["code"],
                "label": sub["label"],
                "icon": sub.get("icon"),
                "sort_order": i,
            })
    counts["submodules"] = _upsert(
        db, CatalogMetaChartSubmodule, submodule_rows,
        conflict_cols=["module_id", "code"],
        update_cols=["label", "icon", "sort_order"],
    )
    db.flush()
    # Indexar por (module_id, code).
    submodule_id_lookup: dict[tuple[int, str], int] = {}
    for s in db.execute(select(CatalogMetaChartSubmodule)).scalars().all():
        submodule_id_lookup[(s.module_id, s.code)] = s.id

    # 3. Chart configs.
    chart_rows: list[dict] = []
    chart_sort = 0
    chart_keys: list[tuple[str, int, int | None, dict]] = []  # (tipo, module_id, submodule_id, chart_dict)

    def _filtro_meta(tipo: str) -> tuple[str, dict]:
        """Deriva (filtro_kind, filtro_params) desde CONFIGS actual.

        Usa el nombre de la función filtro como kind. No serializa callables.
        """
        cfg = CONFIGS.get(tipo)
        if not cfg:
            return ("custom_callable", {})
        f = cfg.get("filtro")
        if f is None:
            return ("all", {})
        fname = getattr(f, "__name__", "unknown")
        return (fname, {})

    def _flags(c: dict, cfg: dict) -> dict:
        return {
            "es_capacidad": bool(cfg.get("es_capacidad", c.get("is_capacity", False))),
            "es_porcentaje": bool(cfg.get("es_porcentaje", False)),
            "es_emision": bool(cfg.get("es_emision", False)),
            "has_loc": bool(c.get("has_loc", False)),
            "has_sub_filtro": bool(c.get("sub_filtros")),
            "soporta_pareto": bool(c.get("soporta_pareto", False)),
            "sub_filtro_label": c.get("sub_filtro_label"),
        }

    def _add_chart(c: dict, module_id: int, submodule_id: int | None):
        nonlocal chart_sort
        tipo = c["tipo"]
        cfg = CONFIGS.get(tipo, {})
        filtro_kind, filtro_params = _filtro_meta(tipo)
        chart_rows.append({
            "tipo": tipo,
            "module_id": module_id,
            "submodule_id": submodule_id,
            "label_titulo": c.get("label") or cfg.get("titulo", tipo),
            "label_figura": cfg.get("figura") or cfg.get("figura_base"),
            "variable_default": cfg.get("variable_default", "UseByTechnology"),
            "filtro_kind": filtro_kind,
            "filtro_params_json": filtro_params,
            "agrupar_por_default": c.get("default_grouping") or cfg.get("agrupar_por", "TECNOLOGIA"),
            "agrupaciones_permitidas_json": c.get("allowed_groupings"),
            "color_fn_key": _color_fn_key(cfg.get("color_fn")),
            "flags_json": _flags(c, cfg),
            "msg_sin_datos": cfg.get("msg_sin_datos"),
            "data_explorer_filters_json": DATA_EXPLORER_FILTERS.get(tipo),
            "is_visible": True,
            "sort_order": chart_sort,
        })
        chart_sort += 1
        chart_keys.append((tipo, module_id, submodule_id, c))

    for m in MENU:
        mod_id = module_id_by_code[m["code"]]
        if m.get("charts"):
            for c in m["charts"]:
                _add_chart(c, mod_id, None)
        if m.get("subsectors"):
            for sub in m["subsectors"]:
                sub_id = submodule_id_lookup.get((mod_id, sub["code"]))
                for c in sub["charts"]:
                    _add_chart(c, mod_id, sub_id)

    counts["charts"] = _upsert(
        db, CatalogMetaChartConfig, chart_rows,
        conflict_cols=["tipo"],
        update_cols=[
            "module_id", "submodule_id", "label_titulo", "label_figura",
            "variable_default", "filtro_kind", "filtro_params_json",
            "agrupar_por_default", "agrupaciones_permitidas_json",
            "color_fn_key", "flags_json", "msg_sin_datos",
            "data_explorer_filters_json", "sort_order",
        ],
    )
    db.flush()

    # 4. Sub-filtros por chart.
    chart_id_by_tipo = dict(
        db.execute(select(CatalogMetaChartConfig.tipo, CatalogMetaChartConfig.id)).all()
    )
    # Borrar sub-filtros existentes de los charts seedeados (reset completo).
    tipos = [t for t, _, _, _ in chart_keys]
    if tipos:
        chart_ids = [chart_id_by_tipo[t] for t in tipos if t in chart_id_by_tipo]
        if chart_ids:
            db.execute(
                delete(CatalogMetaChartSubfilter).where(
                    CatalogMetaChartSubfilter.chart_id.in_(chart_ids)
                )
            )
            db.flush()

    subfilter_rows: list[dict] = []
    for tipo, _mid, _sid, c in chart_keys:
        chart_id = chart_id_by_tipo.get(tipo)
        if not chart_id:
            continue
        subs = c.get("sub_filtros") or []
        label = c.get("sub_filtro_label")
        for i, code in enumerate(subs):
            subfilter_rows.append({
                "chart_id": chart_id,
                "group_label": label,
                "code": code,
                "display_label": None,
                "sort_order": i,
                "default_selected": False,
            })
    if subfilter_rows:
        db.execute(pg_insert(CatalogMetaChartSubfilter).values(subfilter_rows))
        counts["subfilters"] = len(subfilter_rows)

    return counts


def _color_fn_key(fn) -> str:
    """Mapea función de color a un enum serializable."""
    if fn is None:
        return "none"
    name = getattr(fn, "__name__", "")
    mapping = {
        "generar_colores_tecnologias": "tecnologias",
        "_color_electricidad": "electricidad",
        "_color_por_grupo_fijo": "grupo_fijo",
        "_color_por_sector": "por_sector",
        "_color_por_emision": "por_emision",
    }
    return mapping.get(name, "tecnologias")


def seed_variable_units(db: Session) -> dict[str, int]:
    """Unidades por variable.

    Base: PJ para energía/actividad/capacidad, MtCO2eq para emisiones.
    """
    rows = [
        {
            "variable_name": "__DEFAULT_ENERGY__",
            "unit_base": "PJ",
            "display_units_json": [
                {"code": "PJ",  "label": "PJ",  "factor": 1.0},
                {"code": "GW",  "label": "GW",  "factor": 1.0 / 31.536},
                {"code": "MW",  "label": "MW",  "factor": 1.0 / 0.031536},
                {"code": "TWh", "label": "TWh", "factor": 1.0 / 3.6},
                {"code": "Gpc", "label": "Gpc", "factor": 1.0 / 1.0095581216},
            ],
        },
        {
            "variable_name": "__DEFAULT_EMISSION__",
            "unit_base": "MtCO2eq",
            "display_units_json": [
                {"code": "MtCO2eq", "label": "MtCO₂eq", "factor": 1.0},
                {"code": "ktCO2eq", "label": "ktCO₂eq", "factor": 1000.0},
            ],
        },
    ]
    n = _upsert(
        db, CatalogMetaVariableUnit, rows,
        conflict_cols=["variable_name"],
        update_cols=["unit_base", "display_units_json"],
    )
    return {"variable_units": n}


# ---------------------------------------------------------------------------
#  Entrypoint
# ---------------------------------------------------------------------------

SECTIONS = {
    "colors": seed_colors,
    "labels": seed_labels,
    "sectors": seed_sectors,
    "tech_families": seed_tech_families,
    "modules_and_charts": seed_modules_and_charts,
    "variable_units": seed_variable_units,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--section", choices=list(SECTIONS.keys()) + ["all"], default="all")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    total: dict[str, int] = {}
    with SessionLocal() as db:
        sections = list(SECTIONS.keys()) if args.section == "all" else [args.section]
        try:
            for name in sections:
                logger.info("Seeding %s...", name)
                counts = SECTIONS[name](db)
                total.update(counts)
                logger.info("  %s", counts)
            if args.dry_run:
                logger.info("DRY-RUN → rollback")
                db.rollback()
            else:
                db.commit()
                logger.info("Commit OK")
        except Exception:
            db.rollback()
            raise

    logger.info("TOTAL: %s", total)


if __name__ == "__main__":
    main()
