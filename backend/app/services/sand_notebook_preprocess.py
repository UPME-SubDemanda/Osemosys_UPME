"""
Preprocesamiento tipo notebook UPME para paridad exacta con el Jupyter.

Construye sets canónicos, filtra parámetros, completa matrices dispersas con ceros,
aplica ratios de emisión a la entrada y genera matrices UDC y storage.

Pasos aplicados tras la importación SAND:
  1. Construir sets canónicos (desde YearSplit, OutputActivityRatio, EmissionActivityRatio,
     CapacityToActivityUnit): region, technology, fuel, emission, timeslice, mode, year, storage, udc.
  2. Filtrar todos los parámetros: solo conservar filas cuyos índices pertenecen a esos sets.
  3. Completar matrices dispersas: InputActivityRatio, OutputActivityRatio, EmissionActivityRatio,
     VariableCost, TechnologyToStorage, TechnologyFromStorage con valor 0 donde falte.
  4. Emisiones a la entrada: actualizar EmissionActivityRatio con (EmissionActivityRatio × InputActivityRatio)
     para combustible de entrada (como process_and_save_emission_ratios del notebook).
  5. Generar matrices UDC: UDCMultiplierTotalCapacity, UDCMultiplierNewCapacity, UDCMultiplierActivity,
     UDCConstant, UDCTag con combinaciones derivadas de AvailabilityFactor × UDC.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import product

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from app.models import OsemosysParamValue, StorageSet, UdcSet


def _normalize(name: str) -> str:
    """Normaliza nombre de parámetro: minúsculas, solo alfanuméricos."""
    # Estandariza el nombre para comparar parámetros sin depender de mayúsculas,
    # espacios o caracteres especiales. Esto evita bugs por variantes como:
    # "Emission Activity Ratio", "emissionactivityratio", etc.
    return "".join(ch for ch in name.strip().lower() if ch.isalnum())


def _param_key(pv: OsemosysParamValue) -> tuple:
    """Extrae tupla de índices (region, tech, fuel, emission, timeslice, mode, ...) para deduplicar."""
    # Esta clave representa completamente una fila de OsemosysParamValue en términos
    # de dimensionalidad. Se usa para:
    # - saber si una combinación ya existe,
    # - evitar inserts duplicados al completar matrices,
    # - mapear/actualizar valores de forma determinística.
    return (
        pv.id_region,
        pv.id_technology,
        pv.id_fuel,
        pv.id_emission,
        pv.id_timeslice,
        pv.id_mode_of_operation,
        pv.id_season,
        pv.id_daytype,
        pv.id_dailytimebracket,
        pv.id_storage_set,
        pv.id_udc_set,
        pv.year,
    )


def build_canonical_sets(db: Session, scenario_id: int) -> dict[str, set]:
    """
    Construye sets canónicos desde los mismos parámetros que el notebook
    (YearSplit → REGION, TIMESLICE, YEAR; EmissionActivityRatio → EMISSION;
    OutputActivityRatio → TECHNOLOGY, FUEL; CapacityToActivityUnit → REGION, TECHNOLOGY).
    """
    # 1) Cargamos todo el escenario para construir sets en memoria.
    #    Esta función prioriza consistencia con notebook sobre micro-optimización.
    rows = (
        db.execute(
            select(OsemosysParamValue).where(OsemosysParamValue.id_scenario == scenario_id)
        )
        .scalars().all()
    )
    # .scalars().all() puede devolver lista de instancias (ORM) o de Row; normalizar a lista de OsemosysParamValue
    if rows and hasattr(rows[0], "param_name"):
        opv_list = list(rows)
    else:
        opv_list = [r[0] for r in rows]

    # 2) Inicializamos cada set dimensional.
    #    Se permiten None temporalmente para no perder observabilidad durante el barrido;
    #    luego las funciones consumidoras suelen filtrar None cuando aplica.
    regions: set[int | None] = set()
    technologies: set[int | None] = set()
    fuels: set[int | None] = set()
    emissions: set[int | None] = set()
    timeslices: set[int | None] = set()
    modes: set[int | None] = set()
    years: set[int | None] = set()
    storages: set[int | None] = set()
    udcs: set[int | None] = set()

    # 3) Construcción de sets "canónicos" tomando como semilla los mismos parámetros
    #    que el notebook original usa para inferir cardinalidades útiles.
    for pv in opv_list:
        pname = _normalize(pv.param_name)
        if pname == "yearsplit":
            # YearSplit define explícitamente REGION, TIMESLICE y YEAR.
            if pv.id_region is not None:
                regions.add(pv.id_region)
            if pv.id_timeslice is not None:
                timeslices.add(pv.id_timeslice)
            if pv.year is not None:
                years.add(pv.year)
        elif pname == "outputactivityratio":
            # OutputActivityRatio con valor no-cero aporta estructura útil de
            # tecnología/combustible/modo para el modelo.
            if float(pv.value) != 0.0:
                if pv.id_region is not None:
                    regions.add(pv.id_region)
                if pv.id_technology is not None:
                    technologies.add(pv.id_technology)
                if pv.id_fuel is not None:
                    fuels.add(pv.id_fuel)
                if pv.id_mode_of_operation is not None:
                    modes.add(pv.id_mode_of_operation)
            if pv.year is not None:
                years.add(pv.year)
        elif pname == "emissionactivityratio":
            # EmissionActivityRatio no-cero aporta la estructura de emisiones.
            if float(pv.value) != 0.0:
                if pv.id_region is not None:
                    regions.add(pv.id_region)
                if pv.id_technology is not None:
                    technologies.add(pv.id_technology)
                if pv.id_emission is not None:
                    emissions.add(pv.id_emission)
                if pv.id_mode_of_operation is not None:
                    modes.add(pv.id_mode_of_operation)
            if pv.year is not None:
                years.add(pv.year)
        elif pname == "capacitytoactivityunit":
            # CapacityToActivityUnit no-cero aporta pares region-tecnología activos.
            if float(pv.value) != 0.0:
                if pv.id_region is not None:
                    regions.add(pv.id_region)
                if pv.id_technology is not None:
                    technologies.add(pv.id_technology)

        # Storage/UDC se capturan de forma transversal, sin depender de pname.
        if pv.id_storage_set is not None:
            storages.add(pv.id_storage_set)
        if pv.id_udc_set is not None:
            udcs.add(pv.id_udc_set)

    # Si no hay YearSplit, inferir regiones/años desde otros parámetros (fallback)
    # 4) Fallbacks: si el archivo no trae semillas suficientes, inferimos desde
    #    cualquier fila para no quedar con sets vacíos.
    if not regions or not years:
        for pv in opv_list:
            if pv.id_region is not None:
                regions.add(pv.id_region)
            if pv.year is not None:
                years.add(pv.year)
    if not timeslices:
        for pv in opv_list:
            if pv.id_timeslice is not None:
                timeslices.add(pv.id_timeslice)
    if not technologies:
        for pv in opv_list:
            if pv.id_technology is not None:
                technologies.add(pv.id_technology)
    if not fuels:
        for pv in opv_list:
            if pv.id_fuel is not None:
                fuels.add(pv.id_fuel)
    if not modes:
        for pv in opv_list:
            if pv.id_mode_of_operation is not None:
                modes.add(pv.id_mode_of_operation)
    if not emissions:
        for pv in opv_list:
            if pv.id_emission is not None:
                emissions.add(pv.id_emission)

    # 5) Si no hubo datos de storage/udc en el escenario, tomamos catálogos completos
    #    para permitir completar matrices UDC/storage de forma consistente.
    if not storages:
        catalog_storages = db.execute(select(StorageSet.id)).scalars().all()
        storages.update(catalog_storages)
    if not udcs:
        catalog_udcs = db.execute(select(UdcSet.id)).scalars().all()
        udcs.update(catalog_udcs)

    # 6) Entregamos sets consolidados para el resto del pipeline.
    return {
        "region": regions,
        "technology": technologies,
        "fuel": fuels,
        "emission": emissions,
        "timeslice": timeslices,
        "mode_of_operation": modes,
        "year": years,
        "storage": storages,
        "udc": udcs,
    }


def filter_params_by_sets(db: Session, scenario_id: int, sets: dict[str, set]) -> int:
    """Elimina filas de osemosys_param_value cuyos índices no pertenecen a los sets canónicos.

    Ejecuta DELETE ... WHERE directamente en SQL para evitar cargar
    millones de objetos ORM en Python.
    """
    OPV = OsemosysParamValue
    conditions = []
    _dim_checks: list[tuple] = [
        (OPV.id_region, "region"),
        (OPV.id_technology, "technology"),
        (OPV.id_fuel, "fuel"),
        (OPV.id_emission, "emission"),
        (OPV.id_timeslice, "timeslice"),
        (OPV.id_mode_of_operation, "mode_of_operation"),
    ]
    # Construimos reglas "fuera de set": col no nula y valor no permitido.
    for col, set_key in _dim_checks:
        valid_ids = sets.get(set_key)
        if valid_ids:
            conditions.append(and_(col.isnot(None), col.notin_(list(valid_ids))))

    valid_years = sets.get("year")
    if valid_years:
        conditions.append(and_(OPV.year.isnot(None), OPV.year.notin_(list(valid_years))))

    # Si no hay sets válidos que apliquen, no hay nada que filtrar.
    if not conditions:
        return 0

    # Borrado masivo directo en SQL: más eficiente que cargar ORM fila a fila.
    result = db.execute(
        delete(OPV).where(
            OPV.id_scenario == scenario_id,
            or_(*conditions),
        )
    )
    return result.rowcount


def _existing_keys_and_name_by_param(
    db: Session, scenario_id: int, param_name_normalized: str
) -> tuple[set[tuple], str | None]:
    """
    Devuelve (conjunto de claves ya presentes, param_name tal como está en BD).
    Si no hay filas, param_name es None (se usará el nombre pasado a la función).
    """
    # Traemos filas del escenario y nos quedamos solo con el parámetro solicitado
    # (normalizado), para armar el set de claves existentes.
    rows = (
        db.execute(
            select(OsemosysParamValue).where(OsemosysParamValue.id_scenario == scenario_id)
        )
        .scalars().all()
    )
    keys: set[tuple] = set()
    canonical_name: str | None = None
    for row in rows:
        pv = row if hasattr(row, "param_name") else row[0]
        if _normalize(pv.param_name) != param_name_normalized:
            continue
        if canonical_name is None:
            # Conservamos el primer nombre real observado para mantener casing y
            # estilo histórico del dataset.
            canonical_name = pv.param_name
        keys.add(_param_key(pv))
    return keys, canonical_name


def complete_matrix_activity_ratio(
    db: Session, scenario_id: int, sets: dict[str, set], param_name: str
) -> int:
    """
    Completa InputActivityRatio o OutputActivityRatio con todas las combinaciones
    (region, technology, fuel, mode, year); valor 0 donde falte.
    Usa el mismo param_name que ya esté en BD si existe.
    """
    # Normalizamos para identificar filas existentes aunque el casing varíe.
    param_norm = _normalize(param_name)
    existing, canonical_name = _existing_keys_and_name_by_param(db, scenario_id, param_norm)
    param_name_to_use = canonical_name or param_name
    regions = [r for r in sets["region"] if r is not None]
    technologies = [t for t in sets["technology"] if t is not None]
    fuels = [f for f in sets["fuel"] if f is not None]
    modes = [m for m in sets["mode_of_operation"] if m is not None]
    years = [y for y in sets["year"] if y is not None]
    # Si un set viene vacío, usamos [None] para construir un producto mínimo y
    # conservar compatibilidad con escenarios incompletos.
    if not regions:
        regions = [None]
    if not technologies:
        technologies = [None]
    if not fuels:
        fuels = [None]
    if not modes:
        modes = [None]
    if not years:
        years = [None]

    added = 0
    # Recorremos todas las combinaciones esperadas por notebook y creamos faltantes.
    for (id_region, id_technology, id_fuel, id_mode, id_year) in product(
        regions, technologies, fuels, modes, years
    ):
        key = (
            id_region,
            id_technology,
            id_fuel,
            None,  # emission
            None,  # timeslice
            id_mode,
            None, None, None, None, None,
            id_year,
        )
        # Si la combinación ya existe, no insertamos duplicado.
        if key in existing:
            continue
        # Insert de hueco con valor 0.0 (matriz dispersa -> matriz completa).
        db.add(
            OsemosysParamValue(
                id_scenario=scenario_id,
                param_name=param_name_to_use,
                id_region=id_region,
                id_technology=id_technology,
                id_fuel=id_fuel,
                id_emission=None,
                id_timeslice=None,
                id_mode_of_operation=id_mode,
                id_season=None,
                id_daytype=None,
                id_dailytimebracket=None,
                id_storage_set=None,
                id_udc_set=None,
                year=id_year,
                value=0.0,
            )
        )
        added += 1
        existing.add(key)
    return added


def complete_matrix_emission(
    db: Session, scenario_id: int, sets: dict[str, set]
) -> int:
    """Completa EmissionActivityRatio con combinaciones (region, technology, emission, mode, year); 0 donde falte."""
    param_norm = "emissionactivityratio"
    existing, canonical_name = _existing_keys_and_name_by_param(db, scenario_id, param_norm)
    param_name_to_use = canonical_name or "EmissionActivityRatio"
    # Dimensiones esperadas para EmissionActivityRatio:
    # region x technology x emission x mode x year.
    regions = [r for r in sets["region"] if r is not None] or [None]
    technologies = [t for t in sets["technology"] if t is not None] or [None]
    emissions = [e for e in sets["emission"] if e is not None] or [None]
    modes = [m for m in sets["mode_of_operation"] if m is not None] or [None]
    years = [y for y in sets["year"] if y is not None] or [None]

    added = 0
    for (id_region, id_technology, id_emission, id_mode, id_year) in product(
        regions, technologies, emissions, modes, years
    ):
        key = (
            id_region,
            id_technology,
            None,  # fuel
            id_emission,
            None,  # timeslice
            id_mode,
            None, None, None, None, None,
            id_year,
        )
        if key in existing:
            continue
        # Faltante detectado: se agrega con 0.0.
        db.add(
            OsemosysParamValue(
                id_scenario=scenario_id,
                param_name=param_name_to_use,
                id_region=id_region,
                id_technology=id_technology,
                id_fuel=None,
                id_emission=id_emission,
                id_timeslice=None,
                id_mode_of_operation=id_mode,
                id_season=None,
                id_daytype=None,
                id_dailytimebracket=None,
                id_storage_set=None,
                id_udc_set=None,
                year=id_year,
                value=0.0,
            )
        )
        added += 1
        existing.add(key)
    return added


def complete_matrix_variable_cost(
    db: Session, scenario_id: int, sets: dict[str, set]
) -> int:
    """Completa VariableCost con (region, technology, mode, year); 0 donde falte."""
    param_norm = "variablecost"
    existing, canonical_name = _existing_keys_and_name_by_param(db, scenario_id, param_norm)
    param_name_to_use = canonical_name or "VariableCost"
    # Dimensiones de VariableCost: region x technology x mode x year.
    regions = [r for r in sets["region"] if r is not None] or [None]
    technologies = [t for t in sets["technology"] if t is not None] or [None]
    modes = [m for m in sets["mode_of_operation"] if m is not None] or [None]
    years = [y for y in sets["year"] if y is not None] or [None]

    added = 0
    for (id_region, id_technology, id_mode, id_year) in product(
        regions, technologies, modes, years
    ):
        key = (
            id_region,
            id_technology,
            None, None, None, id_mode,
            None, None, None, None, None,
            id_year,
        )
        if key in existing:
            continue
        db.add(
            OsemosysParamValue(
                id_scenario=scenario_id,
                param_name=param_name_to_use,
                id_region=id_region,
                id_technology=id_technology,
                id_fuel=None,
                id_emission=None,
                id_timeslice=None,
                id_mode_of_operation=id_mode,
                id_season=None,
                id_daytype=None,
                id_dailytimebracket=None,
                id_storage_set=None,
                id_udc_set=None,
                year=id_year,
                value=0.0,
            )
        )
        added += 1
        existing.add(key)
    return added


def complete_matrix_storage(
    db: Session, scenario_id: int, sets: dict[str, set], param_name: str
) -> int:
    """Completa TechnologyToStorage o TechnologyFromStorage con (region, technology, storage, mode); 0 donde falte."""
    # Dimensiones de storage:
    # region x technology x storage x mode (sin year en este diseño).
    storages = sets.get("storage", set())
    if not storages:
        return 0
    param_norm = _normalize(param_name)
    existing, canonical_name = _existing_keys_and_name_by_param(db, scenario_id, param_norm)
    param_name_to_use = canonical_name or param_name
    regions = [r for r in sets["region"] if r is not None] or [None]
    technologies = [t for t in sets["technology"] if t is not None] or [None]
    storage_ids = [s for s in storages if s is not None] or [None]
    modes = [m for m in sets["mode_of_operation"] if m is not None] or [None]

    added = 0
    for (id_region, id_technology, id_storage, id_mode) in product(
        regions, technologies, storage_ids, modes
    ):
        key = (
            id_region,
            id_technology,
            None, None, None, id_mode,
            None, None, None, id_storage, None,
            None,
        )
        if key in existing:
            continue
        db.add(
            OsemosysParamValue(
                id_scenario=scenario_id,
                param_name=param_name_to_use,
                id_region=id_region,
                id_technology=id_technology,
                id_fuel=None,
                id_emission=None,
                id_timeslice=None,
                id_mode_of_operation=id_mode,
                id_season=None,
                id_daytype=None,
                id_dailytimebracket=None,
                id_storage_set=id_storage,
                id_udc_set=None,
                year=None,
                value=0.0,
            )
        )
        added += 1
        existing.add(key)
    return added


def _extract_availability_factor_keys(
    db: Session, scenario_id: int
) -> set[tuple[int | None, int | None, int | None]]:
    """Extrae combinaciones únicas (region, technology, year) de AvailabilityFactor."""
    # AvailabilityFactor se usa como base estructural para crear matrices UDC
    # con cardinalidad coherente (region, technology, year).
    rows = (
        db.execute(
            select(OsemosysParamValue).where(OsemosysParamValue.id_scenario == scenario_id)
        )
        .scalars().all()
    )
    keys: set[tuple[int | None, int | None, int | None]] = set()
    for row in rows:
        pv = row if hasattr(row, "param_name") else row[0]
        if _normalize(pv.param_name) == "availabilityfactor":
            keys.add((pv.id_region, pv.id_technology, pv.year))
    return keys


def complete_udc_multiplier(
    db: Session, scenario_id: int, sets: dict[str, set], param_name: str, default_value: float = 0.0
) -> int:
    """
    Completa UDCMultiplierTotalCapacity / NewCapacity / Activity con todas las
    combinaciones (region, technology, udc, year) derivadas de AvailabilityFactor × UDC.
    Replica crear_UDCMultiplier* del notebook.
    """
    # Si no hay UDCs definidos, no se crean multiplicadores.
    udcs = sets.get("udc", set())
    if not udcs:
        return 0

    param_norm = _normalize(param_name)
    existing, canonical_name = _existing_keys_and_name_by_param(db, scenario_id, param_norm)
    param_name_to_use = canonical_name or param_name

    # Priorizamos combinaciones derivadas de AvailabilityFactor.
    af_keys = _extract_availability_factor_keys(db, scenario_id)
    if not af_keys:
        # Fallback si no hay AF: producto de sets básicos.
        regions = [r for r in sets["region"] if r is not None] or [None]
        technologies = [t for t in sets["technology"] if t is not None] or [None]
        years = [y for y in sets["year"] if y is not None] or [None]
        af_keys = set(product(regions, technologies, years))

    udc_ids = [u for u in udcs if u is not None]
    if not udc_ids:
        return 0

    added = 0
    # Para cada (R,T,Y) y cada UDC, creamos fila faltante.
    for (id_region, id_technology, id_year) in af_keys:
        for id_udc in udc_ids:
            key = (
                id_region, id_technology,
                None, None, None, None,
                None, None, None, None,
                id_udc, id_year,
            )
            if key in existing:
                continue
            db.add(
                OsemosysParamValue(
                    id_scenario=scenario_id,
                    param_name=param_name_to_use,
                    id_region=id_region,
                    id_technology=id_technology,
                    id_fuel=None,
                    id_emission=None,
                    id_timeslice=None,
                    id_mode_of_operation=None,
                    id_season=None,
                    id_daytype=None,
                    id_dailytimebracket=None,
                    id_storage_set=None,
                    id_udc_set=id_udc,
                    year=id_year,
                    value=default_value,
                )
            )
            added += 1
            existing.add(key)
    return added


def complete_udc_constant(
    db: Session, scenario_id: int, sets: dict[str, set], default_value: float = 0.0
) -> int:
    """
    Completa UDCConstant con todas las combinaciones (region, udc, year).
    Replica crear_UDC_parametros / UDCConstant del notebook.
    """
    udcs = sets.get("udc", set())
    if not udcs:
        return 0

    param_norm = "udcconstant"
    existing, canonical_name = _existing_keys_and_name_by_param(db, scenario_id, param_norm)
    param_name_to_use = canonical_name or "UDCConstant"

    # UDCConstant usa (region, udc, year).
    regions = [r for r in sets["region"] if r is not None] or [None]
    udc_ids = [u for u in udcs if u is not None]
    years = [y for y in sets["year"] if y is not None] or [None]

    if not udc_ids:
        return 0

    added = 0
    for (id_region, id_udc, id_year) in product(regions, udc_ids, years):
        key = (
            id_region, None,
            None, None, None, None,
            None, None, None, None,
            id_udc, id_year,
        )
        if key in existing:
            continue
        db.add(
            OsemosysParamValue(
                id_scenario=scenario_id,
                param_name=param_name_to_use,
                id_region=id_region,
                id_technology=None,
                id_fuel=None,
                id_emission=None,
                id_timeslice=None,
                id_mode_of_operation=None,
                id_season=None,
                id_daytype=None,
                id_dailytimebracket=None,
                id_storage_set=None,
                id_udc_set=id_udc,
                year=id_year,
                value=default_value,
            )
        )
        added += 1
        existing.add(key)
    return added


def complete_udc_tag(
    db: Session, scenario_id: int, sets: dict[str, set], default_value: float = 2.0
) -> int:
    """
    Completa UDCTag con todas las combinaciones (region, udc).
    Default=2 (libre/sin restricción), 0=≤, 1==.
    Replica crear_UDC_parametros / UDCTag del notebook.
    """
    udcs = sets.get("udc", set())
    if not udcs:
        return 0

    param_norm = "udctag"
    existing, canonical_name = _existing_keys_and_name_by_param(db, scenario_id, param_norm)
    param_name_to_use = canonical_name or "UDCTag"

    # UDCTag usa (region, udc) sin year.
    regions = [r for r in sets["region"] if r is not None] or [None]
    udc_ids = [u for u in udcs if u is not None]

    if not udc_ids:
        return 0

    added = 0
    for (id_region, id_udc) in product(regions, udc_ids):
        key = (
            id_region, None,
            None, None, None, None,
            None, None, None, None,
            id_udc, None,
        )
        if key in existing:
            continue
        db.add(
            OsemosysParamValue(
                id_scenario=scenario_id,
                param_name=param_name_to_use,
                id_region=id_region,
                id_technology=None,
                id_fuel=None,
                id_emission=None,
                id_timeslice=None,
                id_mode_of_operation=None,
                id_season=None,
                id_daytype=None,
                id_dailytimebracket=None,
                id_storage_set=None,
                id_udc_set=id_udc,
                year=None,
                value=default_value,
            )
        )
        added += 1
        existing.add(key)
    return added


def apply_emission_ratios_at_input(db: Session, scenario_id: int) -> int:
    """
    Actualiza EmissionActivityRatio con el producto (EmissionActivityRatio × InputActivityRatio)
    para contabilizar emisiones a la entrada de combustible (como process_and_save_emission_ratios).
    Por cada (region, tech, emission, mode, year) usa el primer InputActivityRatio no nulo
    en (region, tech, mode, year) y hace new_value = emission_ratio * input_ratio.
    Retorna número de filas actualizadas.
    """
    # Cargamos todas las filas del escenario para construir dos vistas:
    # 1) EmissionActivityRatio por clave completa.
    # 2) Primer InputActivityRatio no-cero por (region, tech, mode, year).
    rows = (
        db.execute(
            select(OsemosysParamValue).where(OsemosysParamValue.id_scenario == scenario_id)
        )
        .scalars().all()
    )
    emission_by_key: dict[tuple, float] = {}
    input_first_by_group: dict[tuple, float] = {}  # (region, tech, mode, year) -> first input value

    for row in rows:
        pv = row if hasattr(row, "param_name") else row[0]
        pname = _normalize(pv.param_name)
        key = _param_key(pv)
        if pname == "emissionactivityratio":
            emission_by_key[key] = float(pv.value)
        elif pname == "inputactivityratio" and pv.id_fuel is not None and float(pv.value) != 0:
            # "Primer" input no-cero por grupo, replicando criterio del notebook.
            group_key = (pv.id_region, pv.id_technology, pv.id_mode_of_operation, pv.year)
            if group_key not in input_first_by_group:
                input_first_by_group[group_key] = float(pv.value)

    updated = 0
    # Recorremos emisiones y aplicamos new = emission * input del grupo.
    for key, emit_val in emission_by_key.items():
        if emit_val == 0:
            continue
        id_region, id_technology, _f, id_emission, _ts, id_mode, *_rest = key
        id_year = key[11]
        group_key = (id_region, id_technology, id_mode, id_year)
        input_val = input_first_by_group.get(group_key)
        # Sin input asociado no se puede transformar el ratio.
        if input_val is None:
            continue
        new_val = emit_val * input_val
        if abs(new_val - emit_val) < 1e-12:
            # Evita escrituras innecesarias por diferencias insignificantes.
            continue
        stmt = select(OsemosysParamValue).where(
            OsemosysParamValue.id_scenario == scenario_id,
            OsemosysParamValue.param_name == "EmissionActivityRatio",
            OsemosysParamValue.id_region == id_region,
            OsemosysParamValue.id_technology == id_technology,
            OsemosysParamValue.id_emission == id_emission,
            OsemosysParamValue.id_mode_of_operation == id_mode,
            OsemosysParamValue.year == id_year,
        )
        # En datasets reales pueden existir filas duplicadas para esta clave
        # (por carga histórica o granularidades no colapsadas). En vez de fallar
        # con scalar_one_or_none(), actualizamos todas las coincidencias.
        found_rows = db.execute(stmt).scalars().all()
        if not found_rows:
            continue
        changed_any = False
        for found in found_rows:
            if abs(float(found.value) - new_val) > 1e-12:
                found.value = new_val
                changed_any = True
        if changed_any:
            updated += 1
    return updated


def run_notebook_preprocess(
    db: Session,
    scenario_id: int,
    *,
    filter_by_sets: bool = True,
    complete_matrices: bool = False,
    emission_ratios_at_input: bool = True,
    generate_udc_matrices: bool = False,
) -> dict[str, int]:
    """
    Ejecuta el preprocesamiento tipo notebook para paridad exacta.

    - filter_by_sets: eliminar filas cuyos índices no están en los sets canónicos.
    - complete_matrices: rellenar matrices con 0 donde falte. Desactivado por defecto
      porque data_processing.py usa dropna y Pyomo asume default=0 para parámetros
      ausentes, haciendo innecesarios los ceros explícitos en BD.
    - emission_ratios_at_input: actualizar EmissionActivityRatio con emisión × input.
    - generate_udc_matrices: generar UDCMultiplier*, UDCConstant, UDCTag. Desactivado
      por defecto porque los defaults del modelo Pyomo (0 para multipliers/constant,
      2 para UDCTag) coinciden con los que este paso generaría.
    """
    # Contadores para trazabilidad: útil para debugging/paridad y observabilidad.
    stats: dict[str, int] = {
        "deleted": 0,
        "completed_inputactivityratio": 0,
        "completed_outputactivityratio": 0,
        "completed_emissionactivityratio": 0,
        "completed_variablecost": 0,
        "completed_technologytostorage": 0,
        "completed_technologyfromstorage": 0,
        "completed_udcmultipliertotalcapacity": 0,
        "completed_udcmultipliernewcapacity": 0,
        "completed_udcmultiplieractivity": 0,
        "completed_udcconstant": 0,
        "completed_udctag": 0,
        "emission_updated": 0,
    }
    # 1) Construimos sets canónicos base del escenario.
    sets = build_canonical_sets(db, scenario_id)
    if filter_by_sets:
        # 2) Limpieza de filas fuera de sets.
        stats["deleted"] = filter_params_by_sets(db, scenario_id, sets)
    if complete_matrices:
        # 3) Completado de matrices dispersas (agrega faltantes en 0.0).
        stats["completed_inputactivityratio"] = complete_matrix_activity_ratio(
            db, scenario_id, sets, "InputActivityRatio"
        )
        stats["completed_outputactivityratio"] = complete_matrix_activity_ratio(
            db, scenario_id, sets, "OutputActivityRatio"
        )
        stats["completed_emissionactivityratio"] = complete_matrix_emission(
            db, scenario_id, sets
        )
        stats["completed_variablecost"] = complete_matrix_variable_cost(
            db, scenario_id, sets
        )
        stats["completed_technologytostorage"] = complete_matrix_storage(
            db, scenario_id, sets, "TechnologyToStorage"
        )
        stats["completed_technologyfromstorage"] = complete_matrix_storage(
            db, scenario_id, sets, "TechnologyFromStorage"
        )
    if generate_udc_matrices and sets.get("udc"):
        # 4) Generación de matrices UDC faltantes.
        stats["completed_udcmultipliertotalcapacity"] = complete_udc_multiplier(
            db, scenario_id, sets, "UDCMultiplierTotalCapacity", default_value=0.0
        )
        stats["completed_udcmultipliernewcapacity"] = complete_udc_multiplier(
            db, scenario_id, sets, "UDCMultiplierNewCapacity", default_value=0.0
        )
        stats["completed_udcmultiplieractivity"] = complete_udc_multiplier(
            db, scenario_id, sets, "UDCMultiplierActivity", default_value=0.0
        )
        stats["completed_udcconstant"] = complete_udc_constant(
            db, scenario_id, sets, default_value=0.0
        )
        stats["completed_udctag"] = complete_udc_tag(
            db, scenario_id, sets, default_value=2.0
        )
    if emission_ratios_at_input:
        # 5) Ajuste de emisiones a entrada de combustible.
        stats["emission_updated"] = apply_emission_ratios_at_input(db, scenario_id)
    return stats
