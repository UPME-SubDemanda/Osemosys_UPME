"""Reader del catálogo editable de visualización (Fase 3.2).

Lee ``catalog_meta_*`` de BD y devuelve dicts con las mismas shapes que los
dicts hardcodeados en ``colors.py``, ``labels.py``, ``configs_comparacion.py``.

Estrategia de cache:
    - In-memory con TTL (30 s) por worker. Cuando el admin edita, un contador
      de "versión" en Redis invalida el cache entre los workers. Si Redis
      falla, cada worker opera con su cache TTL local (peor caso: admin
      espera hasta 30 s para ver cambios).

Fallback:
    - Si la tabla está vacía o la query falla, el reader cae a los dicts
      hardcoded existentes — zero regresión durante la transición.

Uso típico:
    from app.visualization.catalog_reader import get_colores_grupos
    palette = get_colores_grupos()  # dict {"NGS": "#1f77b4", ...}
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import (
    CatalogMetaChartConfig,
    CatalogMetaChartModule,
    CatalogMetaChartSubfilter,
    CatalogMetaChartSubfilterGroup,
    CatalogMetaChartSubmodule,
    CatalogMetaColorPalette,
    CatalogMetaLabel,
    CatalogMetaSectorMapping,
    CatalogMetaTechFamily,
    CatalogMetaVariableUnit,
)

logger = logging.getLogger(__name__)

# Cache TTL en segundos. Cambios tardan hasta este valor en propagarse entre workers.
_CACHE_TTL_SECONDS = 30.0

# Clave usada en Redis para versión global; cada write en el admin la incrementa.
_REDIS_VERSION_KEY = "catalog_meta:version"

# Lock para thread-safety — gunicorn/uvicorn multi-thread.
_cache_lock = threading.RLock()

# Cache local: {section_key: (value, loaded_at, version_seen)}
_cache: dict[str, tuple[Any, float, int]] = {}


def _redis_client():
    """Cliente Redis lazy. Retorna None si Redis no está configurado o falla."""
    try:
        import redis  # type: ignore

        settings = get_settings()
        return redis.from_url(settings.redis_url, socket_timeout=0.5)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Redis no disponible: %s", exc)
        return None


def _read_version() -> int:
    """Lee la versión global del catálogo desde Redis. 0 si no disponible."""
    client = _redis_client()
    if client is None:
        return 0
    try:
        v = client.get(_REDIS_VERSION_KEY)
        return int(v) if v is not None else 0
    except Exception:  # noqa: BLE001
        return 0


def bump_version() -> None:
    """Incrementa la versión global — llamar tras cualquier write admin."""
    client = _redis_client()
    if client is None:
        # En desarrollo sin Redis, invalidamos sólo el worker local.
        invalidate_local_cache()
        return
    try:
        client.incr(_REDIS_VERSION_KEY)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo bump_version en Redis: %s", exc)
        invalidate_local_cache()


def invalidate_local_cache() -> None:
    with _cache_lock:
        _cache.clear()


def _cached(
    key: str,
    loader: Callable[[Session], Any],
    fallback: Any,
) -> Any:
    """Devuelve el valor cacheado; recarga si expiró o la versión cambió.

    Si la carga falla, devuelve el fallback sin cachear.
    """
    now = time.monotonic()
    version = _read_version()
    with _cache_lock:
        entry = _cache.get(key)
        if entry is not None:
            value, loaded_at, ver_seen = entry
            fresh = (now - loaded_at) < _CACHE_TTL_SECONDS and ver_seen == version
            if fresh:
                return value

    # Recarga fuera del lock para no bloquear queries concurrentes.
    try:
        with SessionLocal() as db:
            value = loader(db)
        if not value:
            # Tabla vacía → fallback sin cachear (permite re-chequeo tras seed).
            return fallback
        with _cache_lock:
            _cache[key] = (value, now, version)
        return value
    except Exception as exc:  # noqa: BLE001
        logger.warning("catalog_reader fallback %s: %s", key, exc)
        return fallback


# ---------------------------------------------------------------------------
#  Loaders por sección
# ---------------------------------------------------------------------------

def _load_palette(group: str) -> Callable[[Session], dict[str, str]]:
    def _loader(db: Session) -> dict[str, str]:
        rows = db.execute(
            select(CatalogMetaColorPalette.key, CatalogMetaColorPalette.color_hex)
            .where(CatalogMetaColorPalette.group == group)
            .order_by(CatalogMetaColorPalette.sort_order.asc())
        ).all()
        return {k: c for k, c in rows}
    return _loader


def get_colores_grupos() -> dict[str, str]:
    from app.visualization.colors import COLORES_GRUPOS as DEFAULT
    return _cached("palette:fuel", _load_palette("fuel"), DEFAULT)


def get_color_map_pwr() -> dict[str, str]:
    from app.visualization.colors import COLOR_MAP_PWR as DEFAULT
    return _cached("palette:pwr", _load_palette("pwr"), DEFAULT)


def get_colores_sector() -> dict[str, str]:
    from app.visualization.configs_comparacion import COLORES_SECTOR as DEFAULT
    return _cached("palette:sector", _load_palette("sector"), DEFAULT)


def get_colores_emisiones() -> dict[str, str]:
    from app.visualization.colors import COLORES_EMISIONES as DEFAULT
    return _cached("palette:emission", _load_palette("emission"), DEFAULT)


def get_color_base_familia() -> dict[str, str]:
    from app.visualization.colors import COLOR_BASE_FAMILIA as DEFAULT
    return _cached("palette:family", _load_palette("family"), DEFAULT)


# ---------------------------------------------------------------------------

def _load_mapa_sector(db: Session) -> dict[str, str]:
    """Prefijo tech → sector.

    Fuente preferida: labels con category='sector'. Fallback:
    ``catalog_meta_sector_mapping`` (dejado por compatibilidad histórica).
    """
    # 1. Labels category='sector' (fuente editable vía pestaña Etiquetas).
    label_rows = db.execute(
        select(CatalogMetaLabel.code, CatalogMetaLabel.label_es)
        .where(CatalogMetaLabel.category == "sector")
    ).all()
    if label_rows:
        return {code: name for code, name in label_rows}

    # 2. Fallback a la tabla legacy.
    rows = db.execute(
        select(CatalogMetaSectorMapping.tech_prefix, CatalogMetaSectorMapping.sector_name)
        .order_by(CatalogMetaSectorMapping.sort_order.asc())
    ).all()
    return {p: s for p, s in rows}


def get_mapa_sector() -> dict[str, str]:
    from app.visualization.configs_comparacion import MAPA_SECTOR as DEFAULT
    return _cached("mapa_sector", _load_mapa_sector, DEFAULT)


def _load_familias_tec(db: Session) -> dict[str, list[str]]:
    rows = db.execute(
        select(CatalogMetaTechFamily.family_code, CatalogMetaTechFamily.tech_prefix)
        .order_by(CatalogMetaTechFamily.family_code.asc(), CatalogMetaTechFamily.sort_order.asc())
    ).all()
    out: dict[str, list[str]] = {}
    for fam, pref in rows:
        out.setdefault(fam, []).append(pref)
    return out


def get_familias_tec() -> dict[str, list[str]]:
    from app.visualization.colors import FAMILIAS_TEC as DEFAULT
    return _cached("familias_tec", _load_familias_tec, DEFAULT)


# ---------------------------------------------------------------------------
#  Labels
# ---------------------------------------------------------------------------

def _load_display_names(db: Session) -> dict[str, str]:
    """Etiquetas de tecnología/fuel/emission (cualquier código no-prefijado)."""
    rows = db.execute(
        select(CatalogMetaLabel.code, CatalogMetaLabel.label_es)
        .where(
            # Excluir entradas con prefijo FUEL:: / VAR_CAP:: — esas se
            # sirven por getters dedicados.
            ~CatalogMetaLabel.code.like("FUEL::%"),
            ~CatalogMetaLabel.code.like("VAR_CAP::%"),
        )
    ).all()
    return {c: l for c, l in rows}


def get_display_names() -> dict[str, str]:
    from app.visualization.labels import DISPLAY_NAMES as DEFAULT
    return _cached("display_names", _load_display_names, DEFAULT)


def _load_nombres_combustibles(db: Session) -> dict[str, str]:
    rows = db.execute(
        select(CatalogMetaLabel.code, CatalogMetaLabel.label_es)
        .where(CatalogMetaLabel.code.like("FUEL::%"))
    ).all()
    return {c.replace("FUEL::", "", 1): l for c, l in rows}


def get_nombres_combustibles() -> dict[str, str]:
    from app.visualization.configs import NOMBRES_COMBUSTIBLES as DEFAULT
    return _cached("nombres_combustibles", _load_nombres_combustibles, DEFAULT)


def _load_titulos_variables_capacidad(db: Session) -> dict[str, str]:
    rows = db.execute(
        select(CatalogMetaLabel.code, CatalogMetaLabel.label_es)
        .where(CatalogMetaLabel.code.like("VAR_CAP::%"))
    ).all()
    return {c.replace("VAR_CAP::", "", 1): l for c, l in rows}


def get_titulos_variables_capacidad() -> dict[str, str]:
    from app.visualization.configs import TITULOS_VARIABLES_CAPACIDAD as DEFAULT
    return _cached("titulos_variables_capacidad", _load_titulos_variables_capacidad, DEFAULT)


# ---------------------------------------------------------------------------
#  Chart catalog (módulos + submódulos + configs + subfiltros)
# ---------------------------------------------------------------------------

def _load_chart_catalog_meta(db: Session) -> dict[str, dict[str, Any]]:
    """Devuelve dict {tipo: {label_titulo, module, submodule, variable_default,
    agrupar_por_default, agrupaciones_permitidas, color_fn_key, flags,
    msg_sin_datos, data_explorer_filters, subfilters, is_visible, sort_order}}.
    """
    modules = {
        m.id: m for m in db.execute(select(CatalogMetaChartModule)).scalars().all()
    }
    submodules = {
        s.id: s for s in db.execute(select(CatalogMetaChartSubmodule)).scalars().all()
    }
    charts = db.execute(select(CatalogMetaChartConfig)).scalars().all()
    # Subfiltros agrupados por chart_id.
    subfilters: dict[int, list[dict[str, Any]]] = {}
    for sf in db.execute(select(CatalogMetaChartSubfilter)).scalars().all():
        subfilters.setdefault(sf.chart_id, []).append({
            "code": sf.code,
            "group_label": sf.group_label,
            "display_label": sf.display_label,
            "sort_order": sf.sort_order,
            "default_selected": bool(sf.default_selected),
        })
    # Grupos de subfiltros combinables.
    sub_groups: dict[int, list[dict[str, Any]]] = {}
    for g in db.execute(select(CatalogMetaChartSubfilterGroup)).scalars().all():
        sub_groups.setdefault(g.chart_id, []).append({
            "group_label": g.group_label,
            "codes": g.subfilter_codes_json,
            "sort_order": g.sort_order,
        })

    out: dict[str, dict[str, Any]] = {}
    for c in charts:
        mod = modules.get(c.module_id)
        sub = submodules.get(c.submodule_id) if c.submodule_id else None
        sfs = sorted(subfilters.get(c.id, []), key=lambda x: x["sort_order"])
        sgs = sorted(sub_groups.get(c.id, []), key=lambda x: x["sort_order"])
        out[c.tipo] = {
            "label_titulo": c.label_titulo,
            "label_figura": c.label_figura,
            "module_code": mod.code if mod else None,
            "module_label": mod.label if mod else None,
            "module_icon": mod.icon if mod else None,
            "submodule_code": sub.code if sub else None,
            "submodule_label": sub.label if sub else None,
            "submodule_icon": sub.icon if sub else None,
            "variable_default": c.variable_default,
            "filtro_kind": c.filtro_kind,
            "filtro_params": c.filtro_params_json,
            "agrupar_por_default": c.agrupar_por_default,
            "agrupaciones_permitidas": c.agrupaciones_permitidas_json,
            "color_fn_key": c.color_fn_key,
            "flags": c.flags_json or {},
            "msg_sin_datos": c.msg_sin_datos,
            "data_explorer_filters": c.data_explorer_filters_json,
            "subfilters": sfs,
            "subfilter_groups": sgs,
            "is_visible": bool(c.is_visible),
            "sort_order": c.sort_order,
        }
    return out


def get_chart_catalog_meta() -> dict[str, dict[str, Any]]:
    """Retorna metadatos de BD para cada chart. Dict vacío si la tabla no está poblada."""
    return _cached("chart_catalog_meta", _load_chart_catalog_meta, {})


# ---------------------------------------------------------------------------
#  Unidades
# ---------------------------------------------------------------------------

def _load_variable_units(db: Session) -> dict[str, dict[str, Any]]:
    rows = db.execute(select(CatalogMetaVariableUnit)).scalars().all()
    return {
        r.variable_name: {
            "unit_base": r.unit_base,
            "display_units": r.display_units_json or [],
        }
        for r in rows
    }


def get_variable_units() -> dict[str, dict[str, Any]]:
    return _cached("variable_units", _load_variable_units, {})
