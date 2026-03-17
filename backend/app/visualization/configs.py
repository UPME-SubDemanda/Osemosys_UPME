"""
Configuraciones de gráficas single-escenario.

Basado en osemosys_src/src/configs.py con las siguientes mejoras:
  - Imports ajustados al paquete backend (app.visualization.colors)
  - Lambdas reescritas como funciones nombradas (testabilidad)
  - Campo ``variable_default`` en cada config
  - 3 configs nuevos: prd_electricidad, emisiones_total, emisiones_sectorial
"""

from app.visualization.colors import (
    generar_colores_tecnologias,
    _color_por_grupo_fijo,
    _color_electricidad,
)


# ════════════════════════════════════════════════════════════════════════
# MAPEO DE VARIABLES → TÍTULOS (para capacidad)
# ════════════════════════════════════════════════════════════════════════

TITULOS_VARIABLES_CAPACIDAD = {
    'TotalCapacityAnnual':    'Capacidad Total Anual',
    'NewCapacity':            'Capacidad Nueva',
    'AccumulatedNewCapacity': 'Capacidad Acumulada',
}


# ════════════════════════════════════════════════════════════════════════
# FILTROS NOMBRADOS (reemplazan los lambdas del original)
# ════════════════════════════════════════════════════════════════════════

def _filtro_contiene(df, prefijo: str, sub_filtro=None, **kw):
    """Filtro genérico: TECHNOLOGY *contiene* el texto dado."""
    return df[df['TECHNOLOGY'].str.contains(prefijo)]


def _filtro_pwr(df, **kw):
    """Tecnologías de generación eléctrica (PWR*)."""
    return df[df['TECHNOLOGY'].str.startswith('PWR')]


def _filtro_gas_consumo(df, **kw):
    """Tecnologías que usan gas natural (contienen NGS)."""
    return df[df['TECHNOLOGY'].str.contains('NGS')]


def _filtro_gas_produccion(df, **kw):
    """Tecnologías de producción de gas (UPSREG / MINNGS)."""
    return df[
        df['TECHNOLOGY'].str.startswith('UPSREG')
        | df['TECHNOLOGY'].str.startswith('MINNGS')
    ]


def _filtro_ref_total(df, **kw):
    """Tecnologías de refinería (UPSREF)."""
    return df[df['TECHNOLOGY'].str.startswith('UPSREF')]


def _filtro_ref_import(df, **kw):
    """Refinerías + importaciones."""
    return df[
        df['TECHNOLOGY'].str.startswith('UPSREF')
        | df['TECHNOLOGY'].str.startswith('IMPLPG')
        | df['TECHNOLOGY'].str.startswith('IMPDSL')
        | df['TECHNOLOGY'].str.startswith('IMPGSL')
    ]


def _filtro_residencial(df, sub_filtro=None, loc=None, **kw):
    """
    Filtro para tecnologías residenciales con lógica URB/RUR/ZNI.

    sub_filtro : str | None  → ej. 'CKN', 'WHT', 'AIR'
    loc        : str | None  → 'URB', 'RUR', 'ZNI'
    """
    mask = df['TECHNOLOGY'].str.startswith('DEMRES')

    if sub_filtro:
        mask &= df['TECHNOLOGY'].str.contains(sub_filtro)

    if loc == 'URB':
        mask &= ~df['TECHNOLOGY'].str.contains('RUR')
        mask &= ~df['TECHNOLOGY'].str.contains('ZNI')
    elif loc == 'RUR':
        mask &= df['TECHNOLOGY'].str.contains('RUR')
        mask &= ~df['TECHNOLOGY'].str.contains('ZNI')
    elif loc == 'ZNI':
        mask &= ~df['TECHNOLOGY'].str.contains('RUR')
        mask &= df['TECHNOLOGY'].str.contains('ZNI')

    return df[mask]


def _filtro_prefijo_con_sub(df, prefijo: str, sub_filtro=None, **kw):
    """Filtro genérico: startswith(prefijo) + contains(sub_filtro)."""
    mask = df['TECHNOLOGY'].str.startswith(prefijo)
    if sub_filtro:
        mask &= df['TECHNOLOGY'].str.contains(sub_filtro)
    return df[mask]


def _filtro_industrial(df, sub_filtro=None, **kw):
    return _filtro_prefijo_con_sub(df, 'DEMIND', sub_filtro)


def _filtro_transporte(df, sub_filtro=None, **kw):
    return _filtro_prefijo_con_sub(df, 'DEMTRA', sub_filtro)


def _filtro_terciario(df, sub_filtro=None, **kw):
    return _filtro_prefijo_con_sub(df, 'DEMTER', sub_filtro)


def _filtro_otros(df, sub_filtro=None, **kw):
    if sub_filtro:
        return df[df['TECHNOLOGY'].str.startswith(sub_filtro)]
    return df.iloc[0:0]


def _filtro_construccion(df, sub_filtro=None, **kw):
    return _filtro_prefijo_con_sub(df, 'DEMCON', sub_filtro)


def _filtro_agroforestal(df, sub_filtro=None, **kw):
    return _filtro_prefijo_con_sub(df, 'DEMAGF', sub_filtro)


def _filtro_mineria(df, sub_filtro=None, **kw):
    return _filtro_prefijo_con_sub(df, 'DEMMIN', sub_filtro)


def _filtro_coquerias(df, sub_filtro=None, **kw):
    return _filtro_prefijo_con_sub(df, 'DEMCOQ', sub_filtro)


def _filtro_solidos_extraccion(df, **kw):
    return df[df['TECHNOLOGY'].str.startswith('MINCOA')]


def _filtro_h2(df, **kw):
    """Tecnologías que producen/consumen hidrógeno (filtro por FUEL, no TECHNOLOGY)."""
    if 'FUEL' not in df.columns:
        return df.iloc[0:0]
    return df[(df['FUEL'] == 'HDG') | (df['FUEL'] == 'HDG002')]


def _filtro_ups_refinacion(df, **kw):
    """Upstream refinación: UPSSAF, UPSALK, UPSPEM (biocombustibles e hidrógeno)."""
    return df[
        df['TECHNOLOGY'].str.startswith('UPSSAF')
        | df['TECHNOLOGY'].str.startswith('UPSALK')
        | df['TECHNOLOGY'].str.startswith('UPSPEM')
    ]


def _filtro_min_hidrocarburos(df, **kw):
    """Minería petróleo y gas (MINOIL, MINNGS)."""
    return df[
        df['TECHNOLOGY'].str.startswith('MINOIL')
        | df['TECHNOLOGY'].str.startswith('MINNGS')
    ]


def _filtro_min_carbon(df, **kw):
    """Minería carbón (MINCOA)."""
    return df[df['TECHNOLOGY'].str.startswith('MINCOA')]


def _filtro_solidos_import(df, **kw):
    return df[
        df['TECHNOLOGY'].str.startswith('MINCOA')
        | df['TECHNOLOGY'].str.startswith('IMPCOA')
    ]


def _filtro_solidos_flujos(df, **kw):
    return df[
        df['TECHNOLOGY'].str.startswith('MINCOA')
        | df['TECHNOLOGY'].str.startswith('IMPCOA')
        | df['TECHNOLOGY'].str.startswith('EXPCOA')
    ]


def _filtro_saf_produccion(df, **kw):
    return df[
        df['TECHNOLOGY'].str.startswith('UPSSAF')
        | df['TECHNOLOGY'].str.startswith('UPSBJS')
    ]


def _filtro_extraccion_min(df, **kw):
    """Tecnologías de extracción: bagazo, petróleo, residuos, biocombustibles, carbón."""
    return df[df['TECHNOLOGY'].str.startswith((
        'MINBAG', 'MINOPL', 'MINWAS', 'MINWAS_ORG', 'MINAFR', 'MINSGC',
        'MINWOO', 'MINCOA',
    ))]


# ════════════════════════════════════════════════════════════════════════
# CONFIGS — VERSIÓN OPTIMIZADA
# ════════════════════════════════════════════════════════════════════════

CONFIGS = {

    # ═══════════════════════════════════════════════════════════════════
    # GAS
    # ═══════════════════════════════════════════════════════════════════
    'gas_consumo': {
        'titulo':           'Consumo de Gas Natural por Tecnología',
        'figura':           'Figura 23',
        'filename':         'Fig23_Consumo_Gas',
        'print':            'CONSUMO DE GAS NATURAL',
        'filtro':           _filtro_gas_consumo,
        'msg_sin_datos':    'Sin tecnologías que usan gas (NGS)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'UseByTechnology',
    },

    'gas_produccion': {
        'titulo':           'Oferta/Producción de Gas Natural por Tecnología',
        'figura':           'Figura 22',
        'filename':         'Fig22_Produccion_Gas',
        'print':            'PRODUCCIÓN DE GAS NATURAL',
        'filtro':           _filtro_gas_produccion,
        'msg_sin_datos':    'Sin tecnologías de producción (UPSREG / MINNGS)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'ProductionByTechnology',
    },

    # ═══════════════════════════════════════════════════════════════════
    # REFINERÍAS
    # ═══════════════════════════════════════════════════════════════════
    'ref_total': {
        'titulo':           'Refinerías - Total',
        'figura':           'Figura 24',
        'filename':         'Fig24_Ref_Total',
        'print':            'REFINERÍAS',
        'filtro':           _filtro_ref_total,
        'msg_sin_datos':    'Sin tecnologías de refinería (UPSREF)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'ProductionByTechnology',
    },

    'ref_import': {
        'titulo':           'Refinerías + Importaciones por Tecnología',
        'figura':           'Figura 25',
        'filename':         'Fig25_Ref_Import',
        'print':            'REFINERÍAS + IMPORTACIONES',
        'filtro':           _filtro_ref_import,
        'msg_sin_datos':    'Sin tecnologías de refinería/importación',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         None,
        'variable_default': 'ProductionByTechnology',
    },

    # ═══════════════════════════════════════════════════════════════════
    # RESIDENCIAL
    # ═══════════════════════════════════════════════════════════════════
    'res_total': {
        'titulo':           'Sector Residencial — Consumo Total por Tecnología',
        'figura':           'Figura 30',
        'filename':         'Fig30_Residencial_Total',
        'print':            'SECTOR RESIDENCIAL (TOTAL)',
        'filtro':           _filtro_residencial,
        'msg_sin_datos':    'Sin tecnologías residenciales (DEMRES)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'UseByTechnology',
    },

    'res_uso': {
        'titulo':           'Sector Residencial — Por Uso',
        'figura':           'Figura 31',
        'filename':         'Fig31_Residencial_Uso',
        'print':            'SECTOR RESIDENCIAL (POR USO)',
        'filtro':           _filtro_residencial,
        'msg_sin_datos':    'Sin tecnologías residenciales (DEMRES)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'ProductionByTechnology',
    },


    # ═══════════════════════════════════════════════════════════════════
    # INDUSTRIAL
    # ═══════════════════════════════════════════════════════════════════
    'ind_total': {
        'titulo':           'Sector Industrial — Consumo Total por Tecnología',
        'figura':           'Figura 40',
        'filename':         'Fig40_Industrial_Total',
        'print':            'SECTOR INDUSTRIAL (TOTAL)',
        'filtro':           _filtro_industrial,
        'msg_sin_datos':    'Sin tecnologías industriales (DEMIND)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'UseByTechnology',
    },

    'ind_uso': {
        'titulo':           'Sector Industrial — Por Uso',
        'figura':           'Figura 41',
        'filename':         'Fig41_Industrial_Uso',
        'print':            'SECTOR INDUSTRIAL (POR USO)',
        'filtro':           _filtro_industrial,
        'msg_sin_datos':    'Sin tecnologías industriales (DEMIND)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'ProductionByTechnology',
    },


    # ═══════════════════════════════════════════════════════════════════
    # TRANSPORTE
    # ═══════════════════════════════════════════════════════════════════
    'tra_total': {
        'titulo':           'Sector Transporte — Consumo Total por Tecnología',
        'figura':           'Figura 50',
        'filename':         'Fig50_Transporte_Total',
        'print':            'SECTOR TRANSPORTE (TOTAL)',
        'filtro':           _filtro_transporte,
        'msg_sin_datos':    'Sin tecnologías de transporte (DEMTRA)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'UseByTechnology',
    },

    'tra_uso': {
        'titulo':           'Sector Transporte — Por Uso',
        'figura':           'Figura 51',
        'filename':         'Fig51_Transporte_Uso',
        'print':            'SECTOR TRANSPORTE (POR USO)',
        'filtro':           _filtro_transporte,
        'msg_sin_datos':    'Sin tecnologías de transporte (DEMTRA)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'ProductionByTechnology',
    },


    # ═══════════════════════════════════════════════════════════════════
    # TERCIARIO
    # ═══════════════════════════════════════════════════════════════════
    'ter_total': {
        'titulo':           'Sector Terciario — Consumo Total por Tecnología',
        'figura':           'Figura 60',
        'filename':         'Fig60_Terciario_Total',
        'print':            'SECTOR TERCIARIO (TOTAL)',
        'filtro':           _filtro_terciario,
        'msg_sin_datos':    'Sin tecnologías terciarias (DEMTER)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'UseByTechnology',
    },

    'ter_uso': {
        'titulo':           'Sector Terciario — Por Uso',
        'figura':           'Figura 61',
        'filename':         'Fig61_Terciario_Uso',
        'print':            'SECTOR TERCIARIO (POR USO)',
        'filtro':           _filtro_terciario,
        'msg_sin_datos':    'Sin tecnologías terciarias (DEMTER)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'ProductionByTechnology',
    },


    # ═══════════════════════════════════════════════════════════════════
    # OTROS SECTORES
    # ═══════════════════════════════════════════════════════════════════
    'otros_total': {
        'titulo':           'Otros Sectores — Consumo Total por Tecnología',
        'figura':           'Figura 70',
        'filename':         'Fig70_Otros_Total',
        'print':            'OTROS SECTORES',
        'filtro':           _filtro_otros,
        'msg_sin_datos':    'Sin tecnologías para el sector especificado',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'UseByTechnology',
    },

    # ═══════════════════════════════════════════════════════════════════
    # CAPACIDAD — CONFIGS UNIFICADOS (1 por sector)
    # ═══════════════════════════════════════════════════════════════════
    'cap_electricidad': {
        'titulo_base':      'Matriz Eléctrica',
        'figura_base':      'CAP-ELEC',
        'filename_base':    'Cap_Electricidad',
        'print_base':       'CAPACIDAD - MATRIZ ELÉCTRICA',
        'filtro':           _filtro_pwr,
        'msg_sin_datos':    'Sin tecnologías de generación eléctrica (PWR)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         _color_electricidad,
        'es_capacidad':     True,
        'variable_default': 'TotalCapacityAnnual',
    },

    'cap_industrial': {
        'titulo_base':      'Sector Industrial',
        'figura_base':      'CAP-IND',
        'filename_base':    'Cap_Industrial',
        'print_base':       'CAPACIDAD - SECTOR INDUSTRIAL',
        'filtro':           _filtro_industrial,
        'msg_sin_datos':    'Sin tecnologías industriales (DEMIND)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'es_capacidad':     True,
        'variable_default': 'TotalCapacityAnnual',
    },

    'cap_terciario': {
        'titulo_base':      'Sector Terciario',
        'figura_base':      'CAP-TER',
        'filename_base':    'Cap_Terciario',
        'print_base':       'CAPACIDAD - SECTOR TERCIARIO',
        'filtro':           _filtro_terciario,
        'msg_sin_datos':    'Sin tecnologías terciarias (DEMTER)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'es_capacidad':     True,
        'variable_default': 'TotalCapacityAnnual',
    },

    'cap_otros': {
        'titulo_base':      'Otros Sectores',
        'figura_base':      'CAP-OTROS',
        'filename_base':    'Cap_Otros',
        'print_base':       'CAPACIDAD - OTROS SECTORES',
        'filtro':           _filtro_otros,
        'msg_sin_datos':    'Sin tecnologías para el sector especificado',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'es_capacidad':     True,
        'variable_default': 'TotalCapacityAnnual',
    },

    # ═══════════════════════════════════════════════════════════════════
    # NUEVOS CONFIGS (Paso 1 — plan de implementación)
    # ═══════════════════════════════════════════════════════════════════

    'prd_electricidad': {
        'titulo_base':      'Producción Eléctrica',
        'figura_base':      'PRD-ELEC',
        'filename_base':    'Prd_Electricidad',
        'print_base':       'PRODUCCIÓN ELÉCTRICA',
        'filtro':           _filtro_pwr,
        'msg_sin_datos':    'Sin tecnologías de generación eléctrica (PWR)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         _color_electricidad,
        'es_porcentaje':    True,
        'variable_default': 'ProductionByTechnology',
    },

    'elec_produccion': {
        'titulo':           'Producción de Electricidad por Tecnología',
        'figura':           'Figura 21',
        'filename':         'Fig21_Produccion_Electricidad',
        'print':            'PRODUCCIÓN DE ELECTRICIDAD',
        'filtro':           _filtro_pwr,
        'msg_sin_datos':    'Sin tecnologías de generación eléctrica (PWR)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         _color_electricidad,
        'variable_default': 'ProductionByTechnology',
    },

    'con_total': {
        'titulo':           'Sector Construcción — Consumo Total por Tecnología',
        'figura':           'Figura 11',
        'filename':         'Fig11_Construccion_Total',
        'print':            'SECTOR CONSTRUCCIÓN',
        'filtro':           _filtro_construccion,
        'msg_sin_datos':    'Sin tecnologías de construcción (DEMCON)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'UseByTechnology',
    },

    'agf_total': {
        'titulo':           'Sector Agroforestal — Consumo Total por Tecnología',
        'figura':           'Figura 22',
        'filename':         'Fig22_Agroforestal_Total',
        'print':            'SECTOR AGROFORESTAL',
        'filtro':           _filtro_agroforestal,
        'msg_sin_datos':    'Sin tecnologías agroforestales (DEMAGF)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'UseByTechnology',
    },

    'min_total': {
        'titulo':           'Sector Minería — Consumo Total por Tecnología',
        'figura':           'Figura 24',
        'filename':         'Fig24_Mineria_Total',
        'print':            'SECTOR MINERÍA',
        'filtro':           _filtro_mineria,
        'msg_sin_datos':    'Sin tecnologías de minería (DEMMIN)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'UseByTechnology',
    },

    'coq_total': {
        'titulo':           'Sector Coquerías — Consumo Total por Tecnología',
        'figura':           'Figura 10',
        'filename':         'Fig10_Coquerias_Total',
        'print':            'SECTOR COQUERÍAS',
        'filtro':           _filtro_coquerias,
        'msg_sin_datos':    'Sin tecnologías de coquerías (DEMCOQ)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'UseByTechnology',
    },

    'solidos_import': {
        'titulo':           'Producción e Importación de Sólidos (Carbón)',
        'figura':           'Figura 23',
        'filename':         'Fig23_Produccion_Solidos',
        'print':            'PRODUCCIÓN E IMPORTACIÓN DE SÓLIDOS',
        'filtro':           _filtro_solidos_import,
        'msg_sin_datos':    'Sin tecnologías de sólidos (MINCOA / IMPCOA)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'ProductionByTechnology',
    },

    'solidos_flujos': {
        'titulo':           'Importaciones y Exportaciones de Sólidos',
        'figura':           'Figura 26',
        'filename':         'Fig26_Import_Export_Solidos',
        'print':            'FLUJOS DE SÓLIDOS',
        'filtro':           _filtro_solidos_flujos,
        'msg_sin_datos':    'Sin tecnologías de sólidos (MINCOA / IMPCOA / EXPCOA)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'ProductionByTechnology',
    },

    'solidos_extraccion': {
        'titulo':           'Extracción de Sólidos (Carbón)',
        'figura':           'Figura 25',
        'filename':         'Fig25_Extraccion_Solidos',
        'print':            'EXTRACCIÓN DE SÓLIDOS',
        'filtro':           _filtro_solidos_extraccion,
        'msg_sin_datos':    'Sin tecnologías de minería de sólidos (MINCOA)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'ProductionByTechnology',
    },

    'extraccion_min': {
        'titulo':           'Extracción por Tecnología y Combustible',
        'figura':           'Figura 44',
        'filename':         'Fig44_Extraccion_MIN',
        'print':            'EXTRACCIÓN',
        'filtro':           _filtro_extraccion_min,
        'msg_sin_datos':    'Sin tecnologías de extracción (MIN*)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'ProductionByTechnology',
    },

    'ref_capacidad': {
        'titulo_base':      'Capacidad de Refinación por Derivado',
        'figura_base':      'Figura 27',
        'filename_base':    'Fig27_Refineria_Capacidad',
        'print_base':       'CAPACIDAD DE REFINERÍA',
        'filtro':           _filtro_ref_total,
        'msg_sin_datos':    'Sin tecnologías de refinería (UPSREF)',
        'agrupar_por':      'FUEL',
        'color_fn':         _color_por_grupo_fijo,
        'es_capacidad':     True,
        'variable_default': 'TotalCapacityAnnual',
    },

    'saf_produccion': {
        'titulo':           'Producción SAF por Tecnología',
        'figura':           'Figura 47',
        'filename':         'Fig47_Produccion_SAF',
        'print':            'PRODUCCIÓN SAF',
        'filtro':           _filtro_saf_produccion,
        'msg_sin_datos':    'Sin tecnologías SAF (UPSSAF / UPSBJS)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'ProductionByTechnology',
    },

    'cap_h2': {
        'titulo':           'Producción de Hidrógeno por Tecnología',
        'figura':           'Figura 32',
        'filename':         'Fig32_Produccion_H2',
        'print':            'PRODUCCIÓN DE HIDRÓGENO',
        'filtro':           _filtro_h2,
        'msg_sin_datos':    'Sin tecnologías que producen hidrógeno (FUEL=HDG/HDG002)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'ProductionByTechnology',
    },

    'h2_consumo': {
        'titulo':           'Consumo de Hidrógeno por Tecnología',
        'figura':           'Figura 33',
        'filename':         'Fig33_Consumo_H2',
        'print':            'CONSUMO DE HIDRÓGENO',
        'filtro':           _filtro_h2,
        'msg_sin_datos':    'Sin tecnologías que consumen hidrógeno (FUEL=HDG/HDG002)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'UseByTechnology',
    },

    'ups_refinacion': {
        'titulo':           'Upstream — Refinación (UPSSAF/UPSALK/UPSPEM)',
        'figura':           'Figura 48',
        'filename':         'Fig48_Upstream_Refinacion',
        'print':            'UPSTREAM REFINACIÓN',
        'filtro':           _filtro_ups_refinacion,
        'msg_sin_datos':    'Sin tecnologías de upstream refinación (UPSSAF/UPSALK/UPSPEM)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'ProductionByTechnology',
    },

    'min_hidrocarburos': {
        'titulo':           'Minería — Petróleo y Gas',
        'figura':           'Figura 49',
        'filename':         'Fig49_Mineria_Hidrocarburos',
        'print':            'MINERÍA PETRÓLEO Y GAS',
        'filtro':           _filtro_min_hidrocarburos,
        'msg_sin_datos':    'Sin tecnologías de minería petróleo/gas (MINOIL/MINNGS)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'ProductionByTechnology',
    },

    'min_carbon': {
        'titulo':           'Minería — Carbón',
        'figura':           'Figura 53',
        'filename':         'Fig53_Mineria_Carbon',
        'print':            'MINERÍA CARBÓN',
        'filtro':           _filtro_min_carbon,
        'msg_sin_datos':    'Sin tecnologías de minería de carbón (MINCOA)',
        'agrupar_por':      'TECNOLOGIA',
        'color_fn':         generar_colores_tecnologias,
        'variable_default': 'ProductionByTechnology',
    },

    'emisiones_total': {
        'titulo':           'Emisiones Totales Anuales',
        'figura':           'EMI-TOT',
        'filename':         'Emisiones_Total',
        'print':            'EMISIONES TOTALES',
        'filtro':           None,  # Sin filtro por tecnología
        'msg_sin_datos':    'Sin datos de emisiones',
        'agrupar_por':      'YEAR',
        'color_fn':         None,
        'usa_columnas_tipadas': True,
        'variable_default': 'AnnualEmissions',
    },

    'emisiones_sectorial': {
        'titulo':           'Emisiones por Sector',
        'figura':           'EMI-SEC',
        'filename':         'Emisiones_Sectorial',
        'print':            'EMISIONES SECTORIALES',
        'filtro':           None,  # Se agrupa por sector, no se filtra
        'msg_sin_datos':    'Sin datos de emisiones por tecnología',
        'agrupar_por':      'SECTOR',
        'color_fn':         None,
        'variable_default': 'AnnualTechnologyEmission',
    },
}
