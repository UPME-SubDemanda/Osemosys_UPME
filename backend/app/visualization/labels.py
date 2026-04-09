"""
labels.py — Diccionario de nombres para visualización (OSeMOSYS Colombia).

Mapea códigos de tecnología → display_name legible y corto para gráficas.

Uso directo:
    from app.visualization.labels import get_label

    series_name = get_label("DEMINDCOABOI_LOW")
    # → "Ind. Carbón Caldera (Act.)"

Jerarquía de resolución de get_label(code):
    1. Búsqueda exacta en DISPLAY_NAMES
    2. Generación dinámica basada en los segmentos del código
    3. Fallback al código original (sin crash)

El diccionario DISPLAY_NAMES fue construido a partir del archivo
diccionario_osemosys_v2_xlsx_-_Diccionario_v2.csv y cubre ~700 tecnologías.
"""

from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════
# 1. DICCIONARIOS DE APOYO PARA GENERACIÓN DINÁMICA
# ══════════════════════════════════════════════════════════════════════════

# Prefijo de categoría → abreviatura para gráfica
_CAT_PREFIX: dict[str, str] = {
    "DEMRES":  "Res.",
    "DEMIND":  "Ind.",
    "DEMTRA":  "Tra.",
    "DEMTER":  "Ter.",
    "DEMCON":  "Constr.",
    "DEMAGF":  "Agric.",
    "DEMCOQ":  "Coque",
    "DEMCYR":  "Ref.",
    "DEM":     "Dem.",
    "PWRCOG":  "Cogener.",
    "PWR":     "Gen.",
    "MIN":     "Ext.",
    "GRD":     "Red",
    "IMP":     "Imp.",
    "EXP":     "Exp.",
    "BACKSTOP":"Backup",
    "LND":     "Tierra",
}

# Energético embebido en código → label corto
_ENERGETICO: dict[str, str] = {
    "DSL":    "Diésel",
    "ELC":    "Elec.",
    "GSL":    "Gasolina",
    "NGS":    "GN",
    "LPG":    "GLP",
    "WOO":    "Leña",
    "BGS":    "Biogás",
    "BAG":    "Bagazo",
    "COA":    "Carbón",
    "HDG":    "H₂",
    "HYD":    "Hidro",
    "SOL":    "Solar",
    "WND":    "Viento",
    "ONW":    "Eól.Ter.",
    "OFW":    "Eól.Mar.",
    "FOL":    "F.Oil",
    "JET":    "Jet A1",
    "BDL":    "Biodiésel",
    "BET":    "Bioetanol",
    "SAF":    "SAF",
    "BJS":    "JET-SAF",
    "GEO":    "Geotérm.",
    "WAS":    "RSU",
    "OIL":    "Petróleo",
    "URN":    "Nuclear",
    "AFR":    "Res.Agr.",
    "OPL":    "Palma",
    "BIO":    "Biomasa",
    "LNG":    "GNL",
    "SGC":    "Caña",
    "BMET":   "Biometano",
    "BBG":    "Bio-GSL",
    "BDB":    "Bio-DSL",
    "BGB":    "Bio-GBE",
    "CSP":    "CSP",
    "NGS":    "GN",
}

# Tecnología de uso → label corto
_USO: dict[str, str] = {
    "BOI":   "Caldera",
    "FUR":   "Horno",
    "BOT":   "Bote",
    "BUS":   "Bus",
    "MOT":   "Moto",
    "TAX":   "Taxi",
    "TCK":   "Camión",
    "LDV":   "Veh.Lig.",
    "FWD":   "4x4",
    "MIC":   "Microbús",
    "SHP":   "Barco",
    "STT":   "Semirrem.",
    "AIR":   "AC",
    "ILU":   "Ilum.",
    "REF":   "Refrig.",
    "CKN":   "Estufa",
    "MPW":   "Motor",
    "WHT":   "Cal.Agua",
    "TV":    "TV",
    "WSH":   "Lavadora",
    "AVI":   "Aviac.",
    "MET":   "Metro",
    "STO":   "Almac.",
    "RTP":   "FV Techo",
    "TYD":   "T&D",
    "DST":   "T&D",
    "CC":    "CC",
    "CS":    "CS",
    "SMR":   "SMR",
    "REG":   "Regasif.",
    "ACL":   "Aclimat.",
    "OTH":   "Otros",
    "DATA":  "DataCtr.",
    "FAN":   "Ventil.",
    "PEM":   "PEM",
    "ALK":   "Alcalino",
    "BAT":   "Batería",
    "COG":   "Cogener.",
}

# Eficiencia → label corto
_EFIC: dict[str, str] = {
    "_LOW": "(Act.)",
    "_MID": "(Col.)",
    "_HIG": "(Mun.)",
}

# Área/Subtipo → label corto
_AREA: dict[str, str] = {
    "_RUR": "Rural",
    "_URB": "Urb.",
    "_ZNI": "ZNI",
    "_IMU": "Intermunic.",
    "_ART": "Artic.",
    "_BIA": "Biartic.",
    "_CEN": "Central",
    "_SPL": "Split",
    "_AUC": "Autoc.",
    "_FIX": "Fijo",
    "_FLO": "Flotante",
    "_UGE": "Gran esc.",
    "_UPE": "Peq.esc.",
    "_NDC": "No CDC",
    "_IND": "Ind.",
    "_C2P": "5.5t",
    "_CSG": "12t",
    "_ORG": "Org.",
    "_OFS": "Offshore",
    "_ONS": "Onshore",
    "_BAT": "+Bat.",
    "_CCS": "+CCS",
    "_HEV": "HEV",
    "_PHE": "PHEV",
}

# Grupos COLORES_GRUPOS → label legible para comparaciones por combustible
_GRUPO: dict[str, str] = {
    "NGS":   "Gas Natural",
    "DSL":   "Diésel",
    "ELC":   "Electricidad",
    "GSL":   "Gasolina",
    "COA":   "Carbón",
    "LPG":   "GLP",
    "WOO":   "Leña",
    "BGS":   "Biogás",
    "BAG":   "Bagazo",
    "HDG":   "Hidrógeno",
    "HDG002":"Hidrógeno (ind.)",
    "FOL":   "Fuel Oil",
    "BDL":   "Biodiésel",
    "JET":   "Jet A1",
    "WAS":   "RSU",
    "OIL":   "Petróleo",
    "AFR":   "Res. Agr./Forest.",
    "SAF":   "SAF",
    "BJS":   "JET-SAF",
    "OPL":   "Aceite de Palma",
    "SGC":   "Caña de Azúcar",
    "AUT":   "Autoconsumo",
    "PHEV":  "PHEV",
    "HEV":   "HEV",
    "DEMCON":"Construcción",
    "DEMAGF":"Agric. y Pesca",
    "DEMMIN":"Minería",
    "DEMCOQ":"Coque",
}

# ══════════════════════════════════════════════════════════════════════════
# 2. DICCIONARIO ESTÁTICO (generado del CSV)
#    Cubre todos los códigos del diccionario_osemosys_v2.
#    Formato: "CÓDIGO": "Display Name"
# ══════════════════════════════════════════════════════════════════════════

DISPLAY_NAMES: dict[str, str] = {
    # ── Backstop ──────────────────────────────────────────────────────────
    "BACKSTOP 1":   "Backup 1",
    "BACKSTOP 2":   "Backup 2",
    "BACKSTOP_1":   "Backup 1",
    "BACKSTOP_2":   "Backup 2",

    # ── Red / Distribución ────────────────────────────────────────────────
    "BBDDST":       "T&D Bio-DSL",
    "BBGDST":       "T&D Bio-GSL",
    "BDLTYD":       "T&D Biodiésel",
    "BETTYD":       "T&D Bioetanol",
    "COADST":       "T&D Carbón",
    "CTRNGS":       "Transp. GN (constr.)",
    "GRDCOADST":    "Red Carbón T&D",
    "GRDHDGTRN":    "Red H₂ Ducto",
    "GRDLPGDST":    "Red GLP T&D",
    "GRDNGSDST":    "Red GN T&D",
    "GRDNGSTRN":    "Red GN T&D",
    "GRDTYDELC":    "Red Elec. T&D",
    "GRDZNIELC":    "Red Elec. ZNI",
    "HDGDST":       "Transp. H₂ Carretera",

    # ── Importaciones / Exportaciones ─────────────────────────────────────
    "IMPDSL":       "Imp. Diésel",
    "IMPFOL":       "Imp. Fuel Oil",
    "IMPGSL":       "Imp. Gasolina",
    "IMPJET":       "Imp. Jet A1",
    "IMPLNG":       "Imp. GNL",
    "IMPLPG":       "Imp. GLP",
    "IMPOIL":       "Imp. Petróleo",
    "IMPURN":       "Imp. Uranio",
    "EXPOIL":       "Exp. Petróleo",

    # ── Extracción / Recursos ─────────────────────────────────────────────
    "MINCOA":       "Ext. Carbón",
    "MINCSP":       "Pot. CSP",
    "MINDAM":       "Pot. Hidro (Em.)",
    "MINGEO":       "Recursos Geotérm.",
    "MINLND":       "Tierra Cultivable",
    "MINLPG":       "Ext. GLP",
    "MINNGS":       "Ext. GN",
    "MINOFW":       "Pot. Eól.Mar.",
    "MINOFW_FIX":   "Pot. Eól.Mar. Fijo",
    "MINOFW_FLO":   "Pot. Eól.Mar. Flot.",
    "MINOIL":       "Ext. Petróleo",
    "MINOIL_1LIV":  "Ext. Petróleo Liv.",
    "MINOIL_2MID":  "Ext. Petróleo Med.",
    "MINOIL_3PES":  "Ext. Petróleo Pes.",
    "MINONW":       "Pot. Eól.Ter.",
    "MINOPL":       "Prod. Palma (BDL)",
    "MINROR":       "Pot. Hidro (ROR)",
    "MINSGC":       "Prod. Caña (BET)",
    "MINSOL":       "Pot. Solar FV",
    "MINSOL_RTP":   "Pot. Solar Techo",
    "MINURN":       "Prod. Uranio",
    "MINWAS":       "Prod. RSU",
    "MINWAS_ORG":   "Prod. RSU Org.",
    "MINWAT":       "Agua Disponible",
    "MINWOO":       "Ext. Leña",
    "LNDAGR001":    "Tierra Caña",
    "LNDAGR002":    "Tierra Cacao",
    "LNDAGR003":    "Tierra Café",
    "LNDAGR004":    "Tierra Arroz",

    # ── Generación Eléctrica ──────────────────────────────────────────────
    "PWRAFR":           "Gen. Biomasa (AFR)",
    "PWRAFRCCS":        "Gen. Biomasa AFR+CCS",
    "PWRBGS":           "Gen. Biogás",
    "PWRCOA":           "Gen. Carbón",
    "PWRCOACCS":        "Gen. Carbón+CCS",
    "PWRCOG":           "Cogeneración",
    "PWRCOGBAG":        "Cogener. Bagazo",
    "PWRCOGCOF":        "Cogener. Café",
    "PWRCOGHUS":        "Cogener. Cacao",
    "PWRCOGMAZ":        "Cogener. Hojarasca",
    "PWRCOGRAQ":        "Cogener. Raquis",
    "PWRCOGRCE":        "Cogener. Arroz",
    "PWRCSP":           "Gen. CSP",
    "PWRDAM":           "Hidro Embalse",
    "PWRDSL":           "Gen. Diésel",
    "PWRDST":           "Distrib. Elec.",
    "PWRFOIL":          "Gen. Fuel Oil",
    "PWRGEO":           "Gen. Geotérm.",
    "PWRHYDDAM":        "Hidro Embalse",
    "PWRHYDROR":        "Hidro ROR",
    "PWRHYDROR_NDC":    "Hidro ROR (No CDC)",
    "PWRJET":           "Gen. Jet A1",
    "PWRLPG":           "Gen. GLP",
    "PWRNGS":           "Gen. GN",
    "PWRNGSCCS":        "Gen. GN+CCS",
    "PWRNGS_CC":        "Gen. GN CC",
    "PWRNGS_CS":        "Gen. GN CS",
    "PWRNUC":           "Nuclear (SMR)",
    "PWROFIXW":         "Eól. Mar. Fijo",
    "PWROFLOW":         "Eól. Mar. Flot.",
    "PWRONW":           "Eól. Terrestre",
    "PWRROR":           "Hidro ROR",
    "PWRSOL":           "Solar FV",
    "PWRSOLBAT":        "Solar FV+Bat.",
    "PWRSOLRTP":        "Solar FV Techo",
    "PWRSOLRTP_IND":    "Solar FV Techo Ind.",
    "PWRSOLRTP_ZNI":    "Solar FV Techo ZNI",
    "PWRSOLUGE":        "Solar FV Gran esc.",
    "PWRSOLUGE_BAT":    "Solar FV+Bat. Gran esc.",
    "PWRSOLUPE":        "Solar FV Peq.esc.",
    "PWRWAS":           "Gen. RSU",

    # ── Demanda: Agricultura y Pesca ──────────────────────────────────────
    "DEMAGFDSL":    "Agric. Diésel",
    "DEMAGFELC":    "Agric. Elec.",
    "DEMAGFGSL":    "Agric. Gasolina",
    "DEMAGFNGS":    "Agric. GN",
    "DEMAGFTER":    "Agric. Térm.",
    "DEMAGFWOO":    "Agric. Leña",

    # ── Demanda: Construcción ─────────────────────────────────────────────
    "DEMCONSDSL":   "Constr. Diésel",
    "DEMCONSELC":   "Constr. Elec.",
    "DEMCONSGSL":   "Constr. Gasolina",
    "DEMCONSNGS":   "Constr. GN",

    # ── Demanda: Coque ────────────────────────────────────────────────────
    "DEMCOQDSL":    "Coque Diésel",
    "DEMCOQGSL":    "Coque Gasolina",
    "DEMCYRDSL":    "Ref.+Coque Diésel",
    "DEMCYRELC":    "Ref.+Coque Elec.",
    "DEMCYRGSL":    "Ref.+Coque Gasolina",
    "DEMCYRLPG":    "Ref.+Coque GLP",

    # ── Demanda: Industrial — Bagazo ──────────────────────────────────────
    "DEMINDAUTBOI":         "Ind. Autocons. Caldera",
    "DEMINDAUTFUR":         "Ind. Autocons. Horno",
    "DEMINDBAGBOI":         "Ind. Bagazo Caldera",
    "DEMINDBAGBOI_HIG":     "Ind. Bagazo Caldera (Mun.)",
    "DEMINDBAGBOI_LOW":     "Ind. Bagazo Caldera (Act.)",
    "DEMINDBAGBOI_MID":     "Ind. Bagazo Caldera (Col.)",
    "DEMINDBAGFUR":         "Ind. Bagazo Horno",
    "DEMINDBAGFURCCS":      "Ind. Bagazo Horno+CCS",
    "DEMINDBAGFUR_HIG":     "Ind. Bagazo Horno (Mun.)",
    "DEMINDBAGFUR_LOW":     "Ind. Bagazo Horno (Act.)",
    "DEMINDBAGFUR_MID":     "Ind. Bagazo Horno (Col.)",

    # ── Demanda: Industrial — Biogás ──────────────────────────────────────
    "DEMINDBGSBOI_HIG":     "Ind. Biogás Caldera (Mun.)",
    "DEMINDBGSBOI_LOW":     "Ind. Biogás Caldera (Act.)",
    "DEMINDBGSBOI_MID":     "Ind. Biogás Caldera (Col.)",
    "DEMINDBGSFUR_HIG":     "Ind. Biogás Horno (Mun.)",
    "DEMINDBGSFUR_LOW":     "Ind. Biogás Horno (Act.)",
    "DEMINDBGSFUR_MID":     "Ind. Biogás Horno (Col.)",

    # ── Demanda: Industrial — Carbón ──────────────────────────────────────
    "DEMINDCOABOI":         "Ind. Carbón Caldera",
    "DEMINDCOABOICCS":      "Ind. Carbón Caldera+CCS",
    "DEMINDCOABOI_HIG":     "Ind. Carbón Caldera (Mun.)",
    "DEMINDCOABOI_LOW":     "Ind. Carbón Caldera (Act.)",
    "DEMINDCOABOI_MID":     "Ind. Carbón Caldera (Col.)",
    "DEMINDCOAFUR":         "Ind. Carbón Horno",
    "DEMINDCOAFURCCS":      "Ind. Carbón Horno+CCS",
    "DEMINDCOAFUR_HIG":     "Ind. Carbón Horno (Mun.)",
    "DEMINDCOAFUR_LOW":     "Ind. Carbón Horno (Act.)",
    "DEMINDCOAFUR_MID":     "Ind. Carbón Horno (Col.)",
    "DEMINDCOAOTH_LOW":     "Ind. Carbón Otros (Act.)",

    # ── Demanda: Industrial — Diésel ──────────────────────────────────────
    "DEMINDDSLBOI_HIG":     "Ind. Diésel Caldera (Mun.)",
    "DEMINDDSLBOI_LOW":     "Ind. Diésel Caldera (Act.)",
    "DEMINDDSLBOI_MID":     "Ind. Diésel Caldera (Col.)",
    "DEMINDDSLFUR_HIG":     "Ind. Diésel Horno (Mun.)",
    "DEMINDDSLFUR_LOW":     "Ind. Diésel Horno (Act.)",
    "DEMINDDSLFUR_MID":     "Ind. Diésel Horno (Col.)",

    # ── Demanda: Industrial — Electricidad ────────────────────────────────
    "DEMINDELCAIR_HIG":     "Ind. Elec. AC (Mun.)",
    "DEMINDELCAIR_LOW":     "Ind. Elec. AC (Act.)",
    "DEMINDELCAIR_MID":     "Ind. Elec. AC (Col.)",
    "DEMINDELCBOI":         "Ind. Elec. Caldera",
    "DEMINDELCBOI_HIG":     "Ind. Elec. Caldera (Mun.)",
    "DEMINDELCBOI_LOW":     "Ind. Elec. Caldera (Act.)",
    "DEMINDELCBOI_MID":     "Ind. Elec. Caldera (Col.)",
    "DEMINDELCFUR":         "Ind. Elec. Horno",
    "DEMINDELCFUR_HIG":     "Ind. Elec. Horno (Mun.)",
    "DEMINDELCFUR_LOW":     "Ind. Elec. Horno (Act.)",
    "DEMINDELCFUR_MID":     "Ind. Elec. Horno (Col.)",
    "DEMINDELCILU_HIG":     "Ind. Elec. Ilum. (Mun.)",
    "DEMINDELCILU_LOW":     "Ind. Elec. Ilum. (Act.)",
    "DEMINDELCILU_MID":     "Ind. Elec. Ilum. (Col.)",
    "DEMINDELCMPW":         "Ind. Elec. Motor",
    "DEMINDELCMPW_HIG":     "Ind. Elec. Motor (Mun.)",
    "DEMINDELCMPW_LOW":     "Ind. Elec. Motor (Act.)",
    "DEMINDELCMPW_MID":     "Ind. Elec. Motor (Col.)",
    "DEMINDELCOTH_HIG":     "Ind. Elec. Otros (Mun.)",
    "DEMINDELCOTH_LOW":     "Ind. Elec. Otros (Act.)",
    "DEMINDELCOTH_MID":     "Ind. Elec. Otros (Col.)",
    "DEMINDELCREF_HIG":     "Ind. Elec. Refrig. (Mun.)",
    "DEMINDELCREF_LOW":     "Ind. Elec. Refrig. (Act.)",
    "DEMINDELCREF_MID":     "Ind. Elec. Refrig. (Col.)",

    # ── Demanda: Industrial — Fuel Oil ────────────────────────────────────
    "DEMINDFOLOTH_LOW":     "Ind. F.Oil Otros (Act.)",

    # ── Demanda: Industrial — Hidrógeno ───────────────────────────────────
    "DEMINDHDGBOI":         "Ind. H₂ Caldera",
    "DEMINDHDGBOI_HIG":     "Ind. H₂ Caldera (Mun.)",
    "DEMINDHDGBOI_LOW":     "Ind. H₂ Caldera (Act.)",
    "DEMINDHDGFUR":         "Ind. H₂ Horno",

    # ── Demanda: Industrial — GLP ─────────────────────────────────────────
    "DEMINDLPGBOI_HIG":     "Ind. GLP Caldera (Mun.)",
    "DEMINDLPGBOI_LOW":     "Ind. GLP Caldera (Act.)",
    "DEMINDLPGBOI_MID":     "Ind. GLP Caldera (Col.)",
    "DEMINDLPGFUR_HIG":     "Ind. GLP Horno (Mun.)",
    "DEMINDLPGFUR_LOW":     "Ind. GLP Horno (Act.)",
    "DEMINDLPGFUR_MID":     "Ind. GLP Horno (Col.)",

    # ── Demanda: Industrial — Gas Natural ─────────────────────────────────
    "DEMINDNGSBOI":         "Ind. GN Caldera",
    "DEMINDNGSBOICCS":      "Ind. GN Caldera+CCS",
    "DEMINDNGSBOI_HIG":     "Ind. GN Caldera (Mun.)",
    "DEMINDNGSBOI_LOW":     "Ind. GN Caldera (Act.)",
    "DEMINDNGSBOI_MID":     "Ind. GN Caldera (Col.)",
    "DEMINDNGSFUR":         "Ind. GN Horno",
    "DEMINDNGSFURCCS":      "Ind. GN Horno+CCS",
    "DEMINDNGSFURCSS":      "Ind. GN Horno+CCS",
    "DEMINDNGSFUR_HIG":     "Ind. GN Horno (Mun.)",
    "DEMINDNGSFUR_LOW":     "Ind. GN Horno (Act.)",
    "DEMINDNGSFUR_MID":     "Ind. GN Horno (Col.)",

    # ── Demanda: Industrial — Residuos ────────────────────────────────────
    "DEMINDWASBOI_HIG":     "Ind. RSU Caldera (Mun.)",
    "DEMINDWASBOI_LOW":     "Ind. RSU Caldera (Act.)",

    # ── Demanda: Residencial — Electricidad ───────────────────────────────
    "DEMRESELCAIR_HIG":         "Res. Elec. AC (Mun.)",
    "DEMRESELCAIR_LOW":         "Res. Elec. AC (Act.)",
    "DEMRESELCAIR_MID":         "Res. Elec. AC (Col.)",
    "DEMRESELCAIR_PAR_HIG":     "Res. Elec. AC Pared (Mun.)",
    "DEMRESELCAIR_PAR_LOW":     "Res. Elec. AC Pared (Act.)",
    "DEMRESELCAIR_PAR_MID":     "Res. Elec. AC Pared (Col.)",
    "DEMRESELCAIR_POR_HIG":     "Res. Elec. AC Portátil (Mun.)",
    "DEMRESELCAIR_POR_LOW":     "Res. Elec. AC Portátil (Act.)",
    "DEMRESELCAIR_POR_MID":     "Res. Elec. AC Portátil (Col.)",
    "DEMRESELCAIR_SPL_HIG":     "Res. Elec. AC Split (Mun.)",
    "DEMRESELCAIR_SPL_LOW":     "Res. Elec. AC Split (Act.)",
    "DEMRESELCAIR_SPL_MID":     "Res. Elec. AC Split (Col.)",
    "DEMRESELCAIR_HIG_RUR":     "Res. Elec. AC (Mun.) Rural",
    "DEMRESELCAIR_HIG_URB":     "Res. Elec. AC (Mun.) Urb.",
    "DEMRESELCAIR_LOW_RUR":     "Res. Elec. AC (Act.) Rural",
    "DEMRESELCAIR_LOW_URB":     "Res. Elec. AC (Act.) Urb.",
    "DEMRESELCAIR_MID_RUR":     "Res. Elec. AC (Col.) Rural",
    "DEMRESELCAIR_MID_URB":     "Res. Elec. AC (Col.) Urb.",
    "DEMRESELCCKN_HIG":         "Res. Elec. Estufa (Mun.)",
    "DEMRESELCCKN_LOW":         "Res. Elec. Estufa (Act.)",
    "DEMRESELCCKN_MID":         "Res. Elec. Estufa (Col.)",
    "DEMRESELCCKN_HIG_RUR":     "Res. Elec. Estufa (Mun.) Rural",
    "DEMRESELCCKN_HIG_URB":     "Res. Elec. Estufa (Mun.) Urb.",
    "DEMRESELCCKN_LOW_RUR":     "Res. Elec. Estufa (Act.) Rural",
    "DEMRESELCCKN_LOW_URB":     "Res. Elec. Estufa (Act.) Urb.",
    "DEMRESELCCKN_MID_RUR":     "Res. Elec. Estufa (Col.) Rural",
    "DEMRESELCCKN_MID_URB":     "Res. Elec. Estufa (Col.) Urb.",
    "DEMRESELCILU_HIG":         "Res. Elec. Ilum. (Mun.)",
    "DEMRESELCILU_LOW":         "Res. Elec. Ilum. (Act.)",
    "DEMRESELCILU_MID":         "Res. Elec. Ilum. (Col.)",
    "DEMRESELCILU_HIG_RUR":     "Res. Elec. Ilum. (Mun.) Rural",
    "DEMRESELCILU_HIG_URB":     "Res. Elec. Ilum. (Mun.) Urb.",
    "DEMRESELCILU_LOW_RUR":     "Res. Elec. Ilum. (Act.) Rural",
    "DEMRESELCILU_LOW_URB":     "Res. Elec. Ilum. (Act.) Urb.",
    "DEMRESELCILU_MID_RUR":     "Res. Elec. Ilum. (Col.) Rural",
    "DEMRESELCILU_MID_URB":     "Res. Elec. Ilum. (Col.) Urb.",
    "DEMRESELCOTH_HIG":         "Res. Elec. Otros (Mun.)",
    "DEMRESELCOTH_LOW":         "Res. Elec. Otros (Act.)",
    "DEMRESELCOTH_MID":         "Res. Elec. Otros (Col.)",
    "DEMRESELCOTH_HIG_RUR":     "Res. Elec. Otros (Mun.) Rural",
    "DEMRESELCOTH_HIG_URB":     "Res. Elec. Otros (Mun.) Urb.",
    "DEMRESELCOTH_LOW_RUR":     "Res. Elec. Otros (Act.) Rural",
    "DEMRESELCOTH_LOW_URB":     "Res. Elec. Otros (Act.) Urb.",
    "DEMRESELCOTH_MID_RUR":     "Res. Elec. Otros (Col.) Rural",
    "DEMRESELCOTH_MID_URB":     "Res. Elec. Otros (Col.) Urb.",
    "DEMRESELCREF_HIG":         "Res. Elec. Refrig. (Mun.)",
    "DEMRESELCREF_LOW":         "Res. Elec. Refrig. (Act.)",
    "DEMRESELCREF_MID":         "Res. Elec. Refrig. (Col.)",
    "DEMRESELCREF_HIG_RUR":     "Res. Elec. Refrig. (Mun.) Rural",
    "DEMRESELCREF_HIG_URB":     "Res. Elec. Refrig. (Mun.) Urb.",
    "DEMRESELCREF_LOW_RUR":     "Res. Elec. Refrig. (Act.) Rural",
    "DEMRESELCREF_LOW_URB":     "Res. Elec. Refrig. (Act.) Urb.",
    "DEMRESELCREF_MID_RUR":     "Res. Elec. Refrig. (Col.) Rural",
    "DEMRESELCREF_MID_URB":     "Res. Elec. Refrig. (Col.) Urb.",
    "DEMRESELCTV_HIG":          "Res. Elec. TV (Mun.)",
    "DEMRESELCTV_LOW":          "Res. Elec. TV (Act.)",
    "DEMRESELCTV_MID":          "Res. Elec. TV (Col.)",
    "DEMRESELCTV_CRT":          "Res. Elec. TV CRT",
    "DEMRESELCTV_HIG_RUR":      "Res. Elec. TV (Mun.) Rural",
    "DEMRESELCTV_HIG_URB":      "Res. Elec. TV (Mun.) Urb.",
    "DEMRESELCTV_LOW_RUR":      "Res. Elec. TV (Act.) Rural",
    "DEMRESELCTV_LOW_URB":      "Res. Elec. TV (Act.) Urb.",
    "DEMRESELCTV_MID_RUR":      "Res. Elec. TV (Col.) Rural",
    "DEMRESELCTV_MID_URB":      "Res. Elec. TV (Col.) Urb.",
    "DEMRESELCWSH_HIG":         "Res. Elec. Lavadora (Mun.)",
    "DEMRESELCWSH_LOW":         "Res. Elec. Lavadora (Act.)",
    "DEMRESELCWSH_MID":         "Res. Elec. Lavadora (Col.)",
    "DEMRESELCWSH_HIG_RUR":     "Res. Elec. Lavadora (Mun.) Rural",
    "DEMRESELCWSH_HIG_URB":     "Res. Elec. Lavadora (Mun.) Urb.",
    "DEMRESELCWSH_LOW_RUR":     "Res. Elec. Lavadora (Act.) Rural",
    "DEMRESELCWSH_LOW_URB":     "Res. Elec. Lavadora (Act.) Urb.",
    "DEMRESELCWSH_MID_RUR":     "Res. Elec. Lavadora (Col.) Rural",
    "DEMRESELCWSH_MID_URB":     "Res. Elec. Lavadora (Col.) Urb.",

    # ── Demanda: Residencial — Cal. de Agua ───────────────────────────────
    "DEMRESELCWHT_HIG":         "Res. Elec. Cal.Agua (Mun.)",
    "DEMRESELCWHT_LOW":         "Res. Elec. Cal.Agua (Act.)",
    "DEMRESELCWHT_MID":         "Res. Elec. Cal.Agua (Col.)",
    "DEMRESELCWHT_DUC_HIG":     "Res. Elec. Ducha (Mun.)",
    "DEMRESELCWHT_DUC_LOW":     "Res. Elec. Ducha (Act.)",
    "DEMRESELCWHT_DUC_MID":     "Res. Elec. Ducha (Col.)",
    "DEMRESELCWHT_PAS_HIG":     "Res. Elec. Cal.Agua Paso (Mun.)",
    "DEMRESELCWHT_PAS_LOW":     "Res. Elec. Cal.Agua Paso (Act.)",
    "DEMRESELCWHT_PAS_MID":     "Res. Elec. Cal.Agua Paso (Col.)",
    "DEMRESELCWHT_TAN_HIG":     "Res. Elec. Cal.Agua Tanque (Mun.)",
    "DEMRESELCWHT_TAN_LOW":     "Res. Elec. Cal.Agua Tanque (Act.)",
    "DEMRESELCWHT_TAN_MID":     "Res. Elec. Cal.Agua Tanque (Col.)",
    "DEMRESGASWHT_HIG":         "Res. Gas Cal.Agua (Mun.)",
    "DEMRESGASWHT_LOW":         "Res. Gas Cal.Agua (Act.)",
    "DEMRESGASWHT_MID":         "Res. Gas Cal.Agua (Col.)",
    "DEMRESLPGWHT_HIG":         "Res. GLP Cal.Agua (Mun.)",
    "DEMRESLPGWHT_LOW":         "Res. GLP Cal.Agua (Act.)",
    "DEMRESLPGWHT_MID":         "Res. GLP Cal.Agua (Col.)",
    "DEMRESSOLWHT_HIG":         "Res. Solar Cal.Agua (Mun.)",
    "DEMRESSOLWHT_LOW":         "Res. Solar Cal.Agua (Act.)",
    "DEMRESSOLWHT_MID":         "Res. Solar Cal.Agua (Col.)",

    # ── Demanda: Residencial — GLP/GN/Biogás Estufa ───────────────────────
    "DEMRESBGSCKN_HIG":         "Res. Biogás Estufa (Mun.)",
    "DEMRESBGSCKN_LOW":         "Res. Biogás Estufa (Act.)",
    "DEMRESBGSCKN_MID":         "Res. Biogás Estufa (Col.)",
    "DEMRESLPGCKN_HIG":         "Res. GLP Estufa (Mun.)",
    "DEMRESLPGCKN_LOW":         "Res. GLP Estufa (Act.)",
    "DEMRESLPGCKN_MID":         "Res. GLP Estufa (Col.)",
    "DEMRESLPGCKN_HIG_RUR":     "Res. GLP Estufa (Mun.) Rural",
    "DEMRESLPGCKN_HIG_URB":     "Res. GLP Estufa (Mun.) Urb.",
    "DEMRESLPGCKN_LOW_RUR":     "Res. GLP Estufa (Act.) Rural",
    "DEMRESLPGCKN_LOW_URB":     "Res. GLP Estufa (Act.) Urb.",
    "DEMRESLPGCKN_MID_RUR":     "Res. GLP Estufa (Col.) Rural",
    "DEMRESLPGCKN_MID_URB":     "Res. GLP Estufa (Col.) Urb.",
    "DEMRESNGSCKN_HIG":         "Res. GN Estufa (Mun.)",
    "DEMRESNGSCKN_LOW":         "Res. GN Estufa (Act.)",
    "DEMRESNGSCKN_MID":         "Res. GN Estufa (Col.)",
    "DEMRESNGSCKN_HIG_RUR":     "Res. GN Estufa (Mun.) Rural",
    "DEMRESNGSCKN_HIG_URB":     "Res. GN Estufa (Mun.) Urb.",
    "DEMRESNGSCKN_LOW_RUR":     "Res. GN Estufa (Act.) Rural",
    "DEMRESNGSCKN_LOW_URB":     "Res. GN Estufa (Act.) Urb.",
    "DEMRESNGSCKN_MID_RUR":     "Res. GN Estufa (Col.) Rural",
    "DEMRESNGSCKN_MID_URB":     "Res. GN Estufa (Col.) Urb.",

    # ── Demanda: Residencial — Leña ───────────────────────────────────────
    "DEMRESWOOCKN_HIG":         "Res. Leña Estufa (Mun.)",
    "DEMRESWOOCKN_LOW":         "Res. Leña Estufa (Act.)",
    "DEMRESWOOCKN_MID":         "Res. Leña Estufa (Col.)",
    "DEMRESWOOCKN_HIG_RUR":     "Res. Leña Estufa (Mun.) Rural",
    "DEMRESWOOCKN_HIG_URB":     "Res. Leña Estufa (Mun.) Urb.",
    "DEMRESWOOCKN_LOW_RUR":     "Res. Leña Estufa (Act.) Rural",
    "DEMRESWOOCKN_LOW_URB":     "Res. Leña Estufa (Act.) Urb.",
    "DEMRESWOOCKN_MID_RUR":     "Res. Leña Estufa (Col.) Rural",
    "DEMRESWOOCKN_MID_URB":     "Res. Leña Estufa (Col.) Urb.",

    # ── Demanda: Residencial — ZNI ────────────────────────────────────────
    "DEMRESZNIBGSCKN_MID":      "Res. ZNI Biogás Estufa (Col.)",
    "DEMRESZNIELCCKN_LOW":      "Res. ZNI Elec. Estufa (Act.)",
    "DEMRESZNIELC_LOW":         "Res. ZNI Elec. Otros (Act.)",
    "DEMRESZNILPGCKN_LOW":      "Res. ZNI GLP Estufa (Act.)",
    "DEMRESZNILPGCKN_MID":      "Res. ZNI GLP Estufa (Col.)",
    "DEMRESZNIWOOCKN_LOW":      "Res. ZNI Leña Estufa (Act.)",
    "DEMRES_MEDPVA_URB":        "Res. Solar Autocons. Urb.",

    # ── Demanda: Terciario — Biogás ───────────────────────────────────────
    "DEMTERBGSCKN_HIG":     "Ter. Biogás Estufa (Mun.)",
    "DEMTERBGSCKN_LOW":     "Ter. Biogás Estufa (Act.)",
    "DEMTERBGSCKN_MID":     "Ter. Biogás Estufa (Col.)",

    # ── Demanda: Terciario — Electricidad ─────────────────────────────────
    "DEMTERELCACL_HIG":         "Ter. Elec. Aclimat. (Mun.)",
    "DEMTERELCACL_LOW":         "Ter. Elec. Aclimat. (Act.)",
    "DEMTERELCACL_MID":         "Ter. Elec. Aclimat. (Col.)",
    "DEMTERELCAIR_CEN_HIG":     "Ter. Elec. AC Central (Mun.)",
    "DEMTERELCAIR_CEN_LOW":     "Ter. Elec. AC Central (Act.)",
    "DEMTERELCAIR_CEN_MID":     "Ter. Elec. AC Central (Col.)",
    "DEMTERELCAIR_HIG":         "Ter. Elec. AC (Mun.)",
    "DEMTERELCAIR_LOW":         "Ter. Elec. AC (Act.)",
    "DEMTERELCAIR_SPL_HIG":     "Ter. Elec. AC Split (Mun.)",
    "DEMTERELCAIR_SPL_LOW":     "Ter. Elec. AC Split (Act.)",
    "DEMTERELCAIR_SPL_MID":     "Ter. Elec. AC Split (Col.)",
    "DEMTERELCBOI":             "Ter. Elec. Caldera",
    "DEMTERELCCKN_HIG":         "Ter. Elec. Estufa (Mun.)",
    "DEMTERELCCKN_LOW":         "Ter. Elec. Estufa (Act.)",
    "DEMTERELCCKN_MID":         "Ter. Elec. Estufa (Col.)",
    "DEMTERELCDATA":            "Ter. Elec. DataCtr.",
    "DEMTERELCFAN_HIG":         "Ter. Elec. Ventil. (Mun.)",
    "DEMTERELCFAN_LOW":         "Ter. Elec. Ventil. (Act.)",
    "DEMTERELCFAN_MID":         "Ter. Elec. Ventil. (Col.)",
    "DEMTERELCILU_CIA":         "Ter. Elec. Ilum. Cinta",
    "DEMTERELCILU_HAL":         "Ter. Elec. Ilum. Halóg.",
    "DEMTERELCILU_HIG":         "Ter. Elec. Ilum. (Mun.)",
    "DEMTERELCILU_LFC":         "Ter. Elec. Ilum. LFC",
    "DEMTERELCILU_LOW":         "Ter. Elec. Ilum. (Act.)",
    "DEMTERELCILU_MID":         "Ter. Elec. Ilum. (Col.)",
    "DEMTERELCILU_VAP":         "Ter. Elec. Ilum. Vapor",
    "DEMTERELCMPW_HIG":         "Ter. Elec. Motor (Mun.)",
    "DEMTERELCMPW_LOW":         "Ter. Elec. Motor (Act.)",
    "DEMTERELCMPW_MID":         "Ter. Elec. Motor (Col.)",
    "DEMTERELCOTH":             "Ter. Elec. Otros",
    "DEMTERELCOTH_HIG":         "Ter. Elec. Otros (Mun.)",
    "DEMTERELCOTH_LOW":         "Ter. Elec. Otros (Act.)",
    "DEMTERELCOTH_MID":         "Ter. Elec. Otros (Col.)",
    "DEMTERELCREF_AUC_HIG":     "Ter. Elec. Refrig. Autoc. (Mun.)",
    "DEMTERELCREF_AUC_LOW":     "Ter. Elec. Refrig. Autoc. (Act.)",
    "DEMTERELCREF_AUC_MID":     "Ter. Elec. Refrig. Autoc. (Col.)",
    "DEMTERELCREF_CEN_HIG":     "Ter. Elec. Refrig. Central (Mun.)",
    "DEMTERELCREF_CEN_LOW":     "Ter. Elec. Refrig. Central (Act.)",
    "DEMTERELCREF_CEN_MID":     "Ter. Elec. Refrig. Central (Col.)",
    "DEMTERELCREF_HIG":         "Ter. Elec. Refrig. (Mun.)",
    "DEMTERELCREF_LOW":         "Ter. Elec. Refrig. (Act.)",

    # ── Demanda: Terciario — Hidrógeno / GLP / GN ────────────────────────
    "DEMTERHDGCKN":         "Ter. H₂ Estufa",
    "DEMTERLGPCKN_LOW":     "Ter. GLP Estufa (Act.)",
    "DEMTERLPGCKN_HIG":     "Ter. GLP Estufa (Mun.)",
    "DEMTERLPGCKN_LOW":     "Ter. GLP Estufa (Act.)",
    "DEMTERLPGCKN_MID":     "Ter. GLP Estufa (Col.)",
    "DEMTERNGSBOI_LOW":     "Ter. GN Caldera (Act.)",
    "DEMTERNGSCKN_HIG":     "Ter. GN Estufa (Mun.)",
    "DEMTERNGSCKN_LOW":     "Ter. GN Estufa (Act.)",

    # ── Demanda: Transporte — Diésel ──────────────────────────────────────
    "DEMTRADSLBOT":         "Tra. Diésel Bote",
    "DEMTRADSLBUS":         "Tra. Diésel Bus",
    "DEMTRADSLBUS_ART":     "Tra. Diésel Bus Artic.",
    "DEMTRADSLBUS_BIA":     "Tra. Diésel Bus Biartic.",
    "DEMTRADSLBUS_IMU":     "Tra. Diésel Bus Intermunic.",
    "DEMTRADSLBUS_URB":     "Tra. Diésel Bus Urb.",
    "DEMTRADSLFWD":         "Tra. Diésel 4x4",
    "DEMTRADSLLDV":         "Tra. Diésel Veh.Lig.",
    "DEMTRADSLMIC":         "Tra. Diésel Microbús",
    "DEMTRADSLMOT":         "Tra. Diésel Moto",
    "DEMTRADSLSHP":         "Tra. Diésel Barco",
    "DEMTRADSLSTT":         "Tra. Diésel Semirrem.",
    "DEMTRADSLTAX":         "Tra. Diésel Taxi",
    "DEMTRADSLTCK":         "Tra. Diésel Camión",
    "DEMTRADSLTCK_C2P":     "Tra. Diésel Cam. 5.5t",
    "DEMTRADSLTCK_CSG":     "Tra. Diésel Cam. 12t",

    # ── Demanda: Transporte — Electricidad ────────────────────────────────
    "DEMTRAELCBOT":         "Tra. Elec. Bote",
    "DEMTRAELCBUS":         "Tra. Elec. Bus",
    "DEMTRAELCBUS_ART":     "Tra. Elec. Bus Artic.",
    "DEMTRAELCBUS_BIA":     "Tra. Elec. Bus Biartic.",
    "DEMTRAELCBUS_IMU":     "Tra. Elec. Bus Intermunic.",
    "DEMTRAELCBUS_URB":     "Tra. Elec. Bus Urb.",
    "DEMTRAELCFWD":         "Tra. BEV 4x4",
    "DEMTRAELCLDV":         "Tra. BEV Veh.Lig.",
    "DEMTRAELCMET":         "Tra. Elec. Metro",
    "DEMTRAELCMIC":         "Tra. Elec. Microbús",
    "DEMTRAELCMOT":         "Tra. Elec. Moto",
    "DEMTRAELCSTT":         "Tra. BEV Semirrem.",
    "DEMTRAELCTAX":         "Tra. Elec. Taxi",
    "DEMTRAELCTCK":         "Tra. BEV Camión",
    "DEMTRAELCTCK_C2P":     "Tra. BEV Cam. 5.5t",
    "DEMTRAELCTCK_CSG":     "Tra. BEV Cam. 12t",

    # ── Demanda: Transporte — Fuel Oil ────────────────────────────────────
    "DEMTRAFOLSHP":         "Tra. F.Oil Barco",

    # ── Demanda: Transporte — Gasolina ────────────────────────────────────
    "DEMTRAGSLBOT":         "Tra. Gasolina Bote",
    "DEMTRAGSLBUS":         "Tra. Gasolina Bus",
    "DEMTRAGSLBUS_ART":     "Tra. Gasolina Bus Artic.",
    "DEMTRAGSLBUS_IMU":     "Tra. Gasolina Bus Intermunic.",
    "DEMTRAGSLFWD":         "Tra. Gasolina 4x4",
    "DEMTRAGSLLDV":         "Tra. Gasolina Veh.Lig.",
    "DEMTRAGSLMIC":         "Tra. Gasolina Microbús",
    "DEMTRAGSLMOT":         "Tra. Gasolina Moto",
    "DEMTRAGSLSTT":         "Tra. Gasolina Semirrem.",
    "DEMTRAGSLTAX":         "Tra. Gasolina Taxi",
    "DEMTRAGSLTCK":         "Tra. Gasolina Camión",
    "DEMTRAGSLTCK_C2P":     "Tra. Gasolina Cam. 5.5t",

    # ── Demanda: Transporte — Hidrógeno ───────────────────────────────────
    "DEMTRAHDGBUS":         "Tra. H₂ Bus",
    "DEMTRAHDGBUS_IMU":     "Tra. H₂ Bus Intermunic.",
    "DEMTRAHDGBUS_URB":     "Tra. H₂ Bus Urb.",
    "DEMTRAHDGFWD":         "Tra. FCEV 4x4",
    "DEMTRAHDGLDV":         "Tra. FCEV Veh.Lig.",
    "DEMTRAHDGMIC":         "Tra. H₂ Microbús",
    "DEMTRAHDGMOT":         "Tra. H₂ Moto",
    "DEMTRAHDGSTT":         "Tra. FCEV Semirrem.",
    "DEMTRAHDGTAX":         "Tra. H₂ Taxi",
    "DEMTRAHDGTCK":         "Tra. FCEV Camión",
    "DEMTRAHDGTCK_CSG":     "Tra. FCEV Cam. 12t",

    # ── Demanda: Transporte — Híbridos ────────────────────────────────────
    "DEMTRAHEVFWD":         "Tra. HEV 4x4 (Diésel)",
    "DEMTRAHEVLDV":         "Tra. HEV Veh.Lig. (GSL)",
    "DEMTRAHYBFWD":         "Tra. PHEV 4x4",
    "DEMTRAHYBLDV":         "Tra. PHEV Veh.Lig.",
    "DEMTRAHYBTAX":         "Tra. PHEV Taxi",
    "DEMTRAHYBTCK":         "Tra. PHEV Camión",
    "DEMTRAPHEVFWD":        "Tra. PHEV 4x4",
    "DEMTRAPHEVLDV":        "Tra. PHEV Veh.Lig.",
    "DEMTRAPHEVTAX":        "Tra. PHEV Taxi",

    # ── Demanda: Transporte — Jet / GN / Mezclas ──────────────────────────
    "DEMTRAJETAIR":         "Tra. Jet A1 Aviac.",
    "DEMTRAJETAVI":         "Tra. Jet A1 Aviac.",
    "DEMTRAJETSAFAVI":      "Tra. JET-SAF Aviac.",
    "DEMTRANGSBUS":         "Tra. GN Bus",
    "DEMTRANGSBUS_ART":     "Tra. GN Bus Artic.",
    "DEMTRANGSBUS_BIA":     "Tra. GN Bus Biartic.",
    "DEMTRANGSBUS_IMU":     "Tra. GN Bus Intermunic.",
    "DEMTRANGSBUS_URB":     "Tra. GN Bus Urb.",
    "DEMTRANGSFWD":         "Tra. GN 4x4",
    "DEMTRANGSLDV":         "Tra. GN Veh.Lig.",
    "DEMTRANGSMIC":         "Tra. GN Microbús",
    "DEMTRANGSMOT":         "Tra. GN Moto",
    "DEMTRANGSSTT":         "Tra. GN Semirrem.",
    "DEMTRANGSTAX":         "Tra. GN Taxi",
    "DEMTRANGSTCK":         "Tra. GN Camión",
    "DEMTRANGSTCK_C2P":     "Tra. GN Cam. 5.5t",
    "DEMTRANGSTCK_CSG":     "Tra. GN Cam. 12t",

    # ── Refinerias ────────────────────────────────────────
    "UPSREG":               "Planta Regasificación",
    "UPSREF_BAR":           "Refinería Barrancabermeja",
    "UPSREF_CAR":           "Refinería Cartagena",

    # ── UPSTREAM y Refinación ─────────────────
    "UPSALK":               "Electrolizador alcalino",
    "UPSPEM":               "Electrolizador PEM",
    "UPSSAF":               "Planta comb. sostenible aviación",
    "UPSBJS":               "Mezcla JET-SAF"
}


# ══════════════════════════════════════════════════════════════════════════
# 3. FUNCIÓN PRINCIPAL DE RESOLUCIÓN
# ══════════════════════════════════════════════════════════════════════════

def _dynamic_label(code: str) -> str:
    """
    Genera un label dinámico para códigos no registrados en DISPLAY_NAMES.
    Descompone el código en sus partes y construye un nombre legible.

    Se aplica solo como fallback cuando el código no está en el diccionario.
    """
    # Intentar label de grupo (NGS, DSL, ELC…)
    if code in _GRUPO:
        return _GRUPO[code]

    parts: list[str] = []
    rest = code

    # Detectar sufijos de eficiencia y área (en orden inverso de especificidad)
    suffix_label = ""
    area_label = ""

    for suffix, label in _EFIC.items():
        if rest.endswith(suffix):
            suffix_label = label
            rest = rest[: -len(suffix)]
            break

    for suffix, label in _AREA.items():
        if rest.endswith(suffix):
            area_label = label
            rest = rest[: -len(suffix)]
            break

    # Detectar categoría por prefijo
    for prefix, abbr in _CAT_PREFIX.items():
        if rest.startswith(prefix):
            parts.append(abbr)
            rest = rest[len(prefix):]
            break

    # Detectar energético
    for eng_code, eng_label in _ENERGETICO.items():
        if rest.startswith(eng_code):
            parts.append(eng_label)
            rest = rest[len(eng_code):]
            break

    # Detectar tecnología de uso
    for uso_code, uso_label in _USO.items():
        if rest.startswith(uso_code) or rest == uso_code:
            parts.append(uso_label)
            break

    if area_label:
        parts.append(area_label)
    if suffix_label:
        parts.append(suffix_label)

    result = " ".join(parts).strip()
    return result if result else code  # fallback final: código original


def get_label(code: str) -> str:
    """
    Retorna el display_name para un código de tecnología OSeMOSYS.

    Parámetros
    ----------
    code : str
        Código de tecnología (ej: "DEMINDCOABOI_LOW", "PWRSOLRTP", "NGS").

    Retorna
    -------
    str
        Nombre legible para mostrar en gráficas.
        Nunca lanza excepción: retorna el código original si no hay mapeo.

    Ejemplos
    --------
    >>> get_label("DEMINDCOABOI_LOW")
    'Ind. Carbón Caldera (Act.)'
    >>> get_label("PWRSOLRTP_ZNI")
    'Solar FV Techo ZNI'
    >>> get_label("NGS")
    'Gas Natural'
    >>> get_label("CODIGO_DESCONOCIDO")
    'CODIGO_DESCONOCIDO'
    """
    if not code:
        return code

    # 1. Búsqueda exacta
    label = DISPLAY_NAMES.get(code)
    if label:
        return label

    # 2. Búsqueda en grupos de combustible (para agrupación COMBUSTIBLE)
    label = _GRUPO.get(code)
    if label:
        return label

    # 3. Generación dinámica
    return _dynamic_label(code)


def get_labels_batch(codes: list[str]) -> dict[str, str]:
    """
    Versión batch de get_label para mayor eficiencia cuando se procesan
    muchos códigos a la vez.

    Retorna un dict {codigo: display_name}.
    """
    return {code: get_label(code) for code in codes}