"""
Colores para gráficas OSeMOSYS.

Basado en osemosys_src/src/colors.py, pero sin dependencias de
matplotlib ni numpy — usa solo colorsys (stdlib).
"""

import colorsys


# ══════════════════════════════════════════════════════════════════════════
# Utilidades internas de conversión de color (reemplazan matplotlib)
# ══════════════════════════════════════════════════════════════════════════


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    """Convierte '#RRGGBB' → (r, g, b) en rango [0, 1]."""
    h = hex_color.lstrip("#")
    return (
        int(h[0:2], 16) / 255.0,
        int(h[2:4], 16) / 255.0,
        int(h[4:6], 16) / 255.0,
    )


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    """Convierte (r, g, b) en rango [0, 1] → '#rrggbb'."""
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Restringe *value* al rango [lo, hi] (reemplaza np.clip)."""
    return max(lo, min(hi, value))


# ══════════════════════════════════════════════════════════════════════════
# 1. COLORES PARA ELECTRICIDAD (POR FAMILIAS)
# ══════════════════════════════════════════════════════════════════════════

FAMILIAS_TEC = {
    "SOLAR": [
        "PWRSOLRTP",
        "PWRSOLRTP_ZNI",
        "PWRSOLUGE",
        "PWRSOLUGE_BAT",
        "PWRSOLUPE",
    ],
    "HIDRO": [
        "PWRHYDDAM",
        "PWRHYDROR",
        "PWRHYDROR_NDC",
    ],
    "EOLICA": [
        "PWRWNDONS",
        "PWRWNDOFS_FIX",
        "PWRWNDOFS_FLO",
    ],
    "TERMICA_FOSIL": [
        "PWRCOA",
        "PWRCOACCS",
        "PWRNGS_CC",
        "PWRNGS_CS",
        "PWRNGSCCS",
        "PWRDSL",
        "PWRFOIL",
        "PWRJET",
        "PWRLPG",
    ],
    "NUCLEAR": [
        "PWRNUC",
    ],
    "BIOMASA_RESIDUOS": [
        "PWRAFR",
        "PWRBGS",
        "PWRWAS",
    ],
    "OTRAS": [
        "PWRCSP",
        "PWRGEO",
        "PWRSTD",
    ],
}

COLOR_BASE_FAMILIA = {
    "SOLAR": "#FDB813",  # amarillo solar intenso
    "HIDRO": "#1F77B4",  # azul hidro
    "EOLICA": "#2CA02C",  # verde eólico
    "TERMICA_FOSIL": "#2B2B2B",  # casi negro (carbón/gas)
    "NUCLEAR": "#7B3F98",  # violeta nuclear
    "BIOMASA_RESIDUOS": "#8C6D31",
    "OTRAS": "#17BECF",  # cian técnico
}


def generar_tonos(color_hex: str, n: int) -> list[str]:
    """Genera *n* tonos de un color base variando luminosidad."""
    color_hex = color_hex.lstrip("#")
    r, g, b = (int(color_hex[i : i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)

    tonos: list[str] = []
    for i in range(n):
        # Luminosidad controlada
        li = 0.35 + 0.35 * i / max(1, n - 1)

        # Mantener saturación baja para térmicas
        si = s if s < 0.2 else min(1.0, s * 1.05)

        ri, gi, bi = colorsys.hls_to_rgb(h, li, si)
        tonos.append(f"#{int(ri * 255):02x}{int(gi * 255):02x}{int(bi * 255):02x}")

    return tonos


def construir_color_map_por_familias(
    familias: dict[str, list[str]],
    colores_base: dict[str, str],
) -> dict[str, str]:
    """Construye mapeo tecnología → color basado en familias."""
    color_map: dict[str, str] = {}

    for familia, tecnologias in familias.items():
        base_color = colores_base[familia]
        tonos = generar_tonos(base_color, len(tecnologias))

        for tech, color in zip(tecnologias, tonos):
            color_map[tech] = color

    return color_map


# MAPA DE COLORES PARA ELECTRICIDAD
COLOR_MAP_PWR = construir_color_map_por_familias(
    FAMILIAS_TEC,
    COLOR_BASE_FAMILIA,
)


# ══════════════════════════════════════════════════════════════════════════
# 2. COLORES PARA OTROS SECTORES (POR COMBUSTIBLE)
# ══════════════════════════════════════════════════════════════════════════

COLORES_GRUPOS = {
    "NGS": "#1f77b4",
    "JET": "#ff7f0e",
    "BGS": "#2ca02c",
    "BDL": "#d62728",
    "WAS": "#9467bd",
    "WOO": "#8c564b",
    "GSL": "#e377c2",
    "COA": "#7f7f7f",
    "ELC": "#bcbd22",
    "BAG": "#bcc2c3",
    "DSL": "#aec7e8",
    "LPG": "#ffbb78",
    "FOL": "#98df8a",
    "AUT": "#ff9896",
    # Crudos (FUEL en UseByTechnology para refinerías).
    # Deben ir ANTES de "OIL" para que asignar_grupo haga match específico
    # (itera por orden de inserción y "OIL" in "OIL_1LIV" sería True).
    "OIL_3PES": "#1f2937",  # Crudo pesado — gris muy oscuro
    "OIL_2MID": "#4b5563",  # Crudo intermedio — gris medio
    "OIL_1LIV": "#9ca3af",  # Crudo liviano — gris claro
    "OIL": "#000000",
    "PHEV": "#c5b0d5",
    "HEV": "#f7b6d2",
    "SAF": "#ffd92f",
    "BJS": "#e5c494",
    "OPL": "#b3b3b3",
    "AFR": "#fbb4ae",
    "SGC": "#b3cde3",
    # Hidrógeno (HDG002 debe ir antes que HDG para asignar_grupo)
    "HDG002": "#0096c7",
    "HDG": "#00b4d8",
    # Petróleos/crudos (orden específico: más largo primero; escala de grises)
    "MINOIL_3PES": "#2d2d2d",  # Crudo pesado - gris oscuro
    "MINOIL_2MID": "#5c5c5c",  # Crudo intermedio - gris medio
    "MINOIL_1LIV": "#8c8c8c",  # Crudo liviano - gris claro
    "MINOIL": "#b0b0b0",  # Petróleo/crudo genérico - gris muy claro
    # Sectores pequeños (fallback cuando no hay combustible en nombre)
    "DEMCON": "#6c757d",
    "DEMAGF": "#28a745",
    "DEMMIN": "#fd7e14",
    "DEMCOQ": "#6f42c1",
}


def asignar_grupo(nombre: str) -> str:
    """Retorna la clave del combustible que aparece dentro de *nombre*.

    Usa la paleta desde BD (con fallback a ``COLORES_GRUPOS``).
    """
    from app.visualization.catalog_reader import get_colores_grupos
    grupos = get_colores_grupos()
    for grupo in grupos:
        if grupo in nombre:
            return grupo
    return "OTRO"


def generar_colores_tecnologias(df, columna: str = "COLOR"):
    """Genera paleta de colores agrupada por combustible base.

    Usa solo colorsys (stdlib) en lugar de matplotlib/numpy.
    """
    from app.visualization.catalog_reader import get_colores_grupos
    colores_grupos = get_colores_grupos()
    df = df.copy()
    df["GRUPO"] = df[columna].apply(asignar_grupo)
    color_dict: dict[str, str] = {}
    orden_final: list[str] = []

    for grupo in sorted(df["GRUPO"].unique()):
        subitems = sorted(df[df["GRUPO"] == grupo][columna].unique())
        base_color = colores_grupos.get(grupo, "#999999")
        rgb = _hex_to_rgb(base_color)
        h, l, s = colorsys.rgb_to_hls(*rgb)
        n = len(subitems)

        for i, item in enumerate(subitems):
            if n <= 3:
                factor = 0.6 + 0.2 * (i / max(n - 1, 1))
                l_adj = _clamp(l * factor)
                new_rgb = colorsys.hls_to_rgb(h, l_adj, s)
            else:
                hue_shift = (i / n) * 0.15
                lightness_shift = 0.45 + 0.4 * (i / (n - 1))
                new_rgb = colorsys.hls_to_rgb((h + hue_shift) % 1.0, lightness_shift, s)

            # Clamp each channel to [0, 1] then convert to hex
            clamped = tuple(_clamp(c) for c in new_rgb)
            color_dict[item] = _rgb_to_hex(*clamped)
            orden_final.append(item)

    return [color_dict[c] for c in orden_final], orden_final


def _ordered_color_list(
    color_dict: dict[str, str], df, columna: str
) -> tuple[list[str], list[str]]:
    """Orden preservado de un dict de colores, con fallback #999999 para desconocidos."""
    grupos = df[columna].dropna().unique()
    orden = [k for k in color_dict if k in grupos]
    for g in grupos:
        if g not in orden:
            orden.append(g)
    return [color_dict.get(g, "#999999") for g in orden], orden


def _color_por_sector(df, columna: str = "COLOR"):
    """Paleta fija según COLORES_SECTOR — para gráficas agrupadas por sector."""
    from app.visualization.catalog_reader import get_colores_sector
    return _ordered_color_list(get_colores_sector(), df, columna)


# ══════════════════════════════════════════════════════════════════════════
# 4. COLORES PARA TIPOS DE EMISIÓN (contaminantes y GEI)
# ══════════════════════════════════════════════════════════════════════════

COLORES_EMISIONES = {
    "EMIC02":    "#e67e22",  # CO₂ - naranja
    "EMICH4":    "#e74c3c",  # CH₄ - rojo
    "EMIN2O":    "#8e44ad",  # N₂O - morado
    "EMIBC":     "#2c3e50",  # Black Carbon - gris muy oscuro
    "EMICO":     "#e91e8c",  # CO - magenta/fucsia
    "EMICOVDM":  "#7f7f7f",  # COV - gris
    "EMINH3":    "#aec7e8",  # NH₃ - azul claro
    "EMINOx":    "#7b3f00",  # NOₓ - marrón
    "EMIPM10":   "#ff69b4",  # PM10 - rosa
    "EMIPM2_5":  "#d62728",  # PM2.5 - rojo medio
    "EMISOx":    "#9467bd",  # SOₓ - violeta
}


def _color_por_emision(df, columna: str = "COLOR"):
    """Paleta fija por tipo de emisión (GEI y contaminantes criterio)."""
    from app.visualization.catalog_reader import get_colores_emisiones
    return _ordered_color_list(get_colores_emisiones(), df, columna)


def _color_por_grupo_fijo(df, columna: str = "COLOR"):
    """Paleta fija según COLORES_GRUPOS — para gas y refinerías."""
    from app.visualization.catalog_reader import get_colores_grupos
    colores_grupos = get_colores_grupos()
    grupos_presentes = df[columna].unique()
    colores = [colores_grupos.get(g, "#333333") for g in grupos_presentes]
    return colores, list(grupos_presentes)


# ══════════════════════════════════════════════════════════════════════════
# 3. FUNCIÓN ESPECÍFICA PARA ELECTRICIDAD
# ══════════════════════════════════════════════════════════════════════════


def _color_electricidad(df, columna: str = "COLOR"):
    """
    Aplica colores por familias a tecnologías de generación eléctrica.

    Usa COLOR_MAP_PWR y FAMILIAS_TEC leídos desde BD (con fallback).
    """
    from app.visualization.catalog_reader import get_color_map_pwr, get_familias_tec

    familias = get_familias_tec()
    color_map = get_color_map_pwr()

    tecnologias_presentes = df[columna].unique()

    orden_familias = [
        "SOLAR",
        "HIDRO",
        "EOLICA",
        "TERMICA_FOSIL",
        "NUCLEAR",
        "BIOMASA_RESIDUOS",
        "OTRAS",
    ]

    orden_final: list[str] = []
    for familia in orden_familias:
        techs_familia = [t for t in familias.get(familia, []) if t in tecnologias_presentes]
        orden_final.extend(sorted(techs_familia))

    techs_clasificadas = {t for fam in familias.values() for t in fam}
    techs_no_clasificadas = [
        t for t in tecnologias_presentes if t not in techs_clasificadas
    ]
    orden_final.extend(sorted(techs_no_clasificadas))

    colores = [color_map.get(t, "#CCCCCC") for t in orden_final]
    return colores, orden_final
