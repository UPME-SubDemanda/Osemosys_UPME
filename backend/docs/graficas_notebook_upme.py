# -*- coding: utf-8 -*-
"""
Módulo de gráficas equivalente al notebook UPME (osemosys_notebook_UPME_OPT_01.ipynb).

Réplica completa de las 19 funciones de graficación + helpers + variables intermedias.
Para usar: llamar setup(instance_obj, sol_obj) antes de invocar las funciones graf_*.

Funciones de gráficas disponibles:
  1. graf_CAP_ELEC          - Capacidad eléctrica por tecnología (TotalCapacityAnnual, NewCapacity, etc.)
  2. graf_Production_by_Tech_ELEC - Producción eléctrica por tecnología (RateOfProduction, ProductionByTechnology)
  3. graf_GAS               - Oferta de gas natural (tecnologías UPSREG, MINNGS)
  4. graf_GAS_consumo       - Consumo de gas natural (tecnologías con NGS)
  5. graf_demand_REF_combustible_TOTAL - Refinerías: demanda total por combustible
  6. graf_demand_REF_combustible_IMPORT - Refinerías: demanda + importaciones

  7. graf_demand_RES_combustible_TOTAL  - Sector residencial: consumo total por combustible
  8. graf_demand_RES_combustible       - Sector residencial: consumo por filtro (ej. cocción)
  9. graf_demand_RES_TEC               - Sector residencial: consumo por tecnología (urbano/rural/ZNI)

 10. graf_demand_IND_combustible_TOTAL  - Sector industrial: consumo total por combustible
 11. graf_demand_ind_combustible        - Sector industrial: consumo por filtro

 12. graf_demand_TRA_combustible_TOTAL  - Sector transporte: consumo total por combustible
 13. graf_demand_TRA_combustible        - Sector transporte: consumo por filtro

 14. graf_demand_TER_combustible_TOTAL  - Sector terciario: consumo total por combustible
 15. graf_demand_OTROS_combustible_TOTAL - Otros sectores (DEMCOQ, DEMAGF): consumo por combustible

 16. graf_emissions         - Emisiones anuales por tecnología (AnnualTechnologyEmission)
 17. graf_CAP_storage       - Capacidad de almacenamiento (StorageUpperLimit)
 18. graf_Op_Storage        - Operación de almacenamiento (NetCharge, RateOfCharge/Discharge)
 19. graf_Op_Storage_SOC    - Estado de carga (StorageLevel, StorageUpperLimit, etc.)

Funciones auxiliares:
  - setup()              - Configura referencias globales instance y sol
  - variable_to_dataframe() - Convierte variable Pyomo o dict a DataFrame
  - sol_variable_to_df()  - Convierte variable de solución a DataFrame
  - generar_tonos()      - Genera paleta de tonos a partir de color hex
  - construir_color_map_por_familias() - Mapa de colores por familia tecnológica
  - asignar_grupo()      - Mapea TECHNOLOGY_FUEL a grupo de combustible
  - generar_colores_tecnologias() - Colores por grupo para gráficas sectoriales
  - compute_intermediate_variables() - Calcula RateOfProduction, ProductionByTechnology, etc.
  - cargar_resultado_json() - Carga JSON de resultado para usar con graf_CAP_ELEC y graf_Production
"""

import colorsys
from colorsys import hls_to_rgb, rgb_to_hls

import numpy as np
import pandas as pd
import plotly.express as px
from matplotlib.colors import to_hex
import matplotlib.colors as mcolors

# ---------------------------------------------------------------------------
# Module-level references (set via setup())
# ---------------------------------------------------------------------------
instance = None
sol = None


def setup(instance_obj, sol_obj=None):
    """Configura las referencias globales al modelo Pyomo resuelto y la solución HiGHS.
    Debe llamarse antes de invocar cualquier función graf_*."""
    global instance, sol
    instance = instance_obj
    sol = sol_obj


# ---------------------------------------------------------------------------
# Helper: variable_to_dataframe (notebook exact)
# ---------------------------------------------------------------------------

def variable_to_dataframe(variable, index_names=None):
    """Convierte variable Pyomo indexada (IndexedVar) o dict {(idx1, idx2, ...): value}
    en DataFrame estándar con columnas personalizables (index_names o IDX1, IDX2, ...)."""
    rows = []

    if isinstance(variable, dict):
        first_key = next(iter(variable))
        n_indices = len(first_key) if isinstance(first_key, tuple) else 1
        if index_names is None:
            columns = [f"IDX{i+1}" for i in range(n_indices)] + ["VALUE"]
        else:
            if len(index_names) != n_indices:
                raise ValueError(
                    f"El número de nombres de índices ({len(index_names)}) "
                    f"no coincide con el número de índices ({n_indices})"
                )
            columns = list(index_names) + ["VALUE"]

        for k, v in variable.items():
            if n_indices == 1:
                rows.append((k, v))
            else:
                rows.append((*k, v))
    else:
        first_idx = next(iter(variable))
        n_indices = len(first_idx) if isinstance(first_idx, tuple) else 1
        if index_names is None:
            columns = [f"IDX{i+1}" for i in range(n_indices)] + ["VALUE"]
        else:
            if len(index_names) != n_indices:
                raise ValueError(
                    f"El número de nombres de índices ({len(index_names)}) "
                    f"no coincide con el número de índices ({n_indices})"
                )
            columns = list(index_names) + ["VALUE"]

        for idx in variable:
            v = variable[idx].value
            if n_indices == 1:
                rows.append((idx, v))
            else:
                rows.append((*idx, v))

    return pd.DataFrame(rows, columns=columns)


def sol_variable_to_df(sol_dict, varname, dimnames):
    """Convierte variable del diccionario de solución a DataFrame, adaptando la longitud
    de los índices a las dimensiones esperadas (dimnames)."""
    if varname not in sol_dict:
        raise ValueError(f"La variable {varname} no está en la solución")

    data = []
    for idx, val in sol_dict[varname].items():
        if not isinstance(idx, tuple):
            idx = (idx,)

        idx_extended = list(idx) + [None] * (len(dimnames) - len(idx))

        row = {dimnames[i]: idx_extended[i] for i in range(len(dimnames))}
        row["VALUE"] = val
        data.append(row)

    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Familias de tecnología eléctrica (PWR) y colores base del notebook UPME
# ---------------------------------------------------------------------------

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
    "SOLAR": "#FDB813",
    "HIDRO": "#1F77B4",
    "EOLICA": "#2CA02C",
    "TERMICA_FOSIL": "#2B2B2B",
    "NUCLEAR": "#7B3F98",
    "BIOMASA_RESIDUOS": "#8C6D31",
    "OTRAS": "#17BECF",
}


def generar_tonos(color_hex, n):
    """Genera n tonos de un color hex base variando luminosidad (HLS)."""
    color_hex = color_hex.lstrip("#")
    r, g, b = tuple(int(color_hex[i : i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    tonos = []
    for i in range(n):
        li = 0.35 + 0.35 * i / max(1, n - 1)
        if s < 0.2:
            si = s
        else:
            si = min(1.0, s * 1.05)
        ri, gi, bi = colorsys.hls_to_rgb(h, li, si)
        tonos.append(f"#{int(ri*255):02x}{int(gi*255):02x}{int(bi*255):02x}")
    return tonos


def construir_color_map_por_familias(familias, colores_base):
    """Construye mapa tecnología -> color hex a partir de familias y colores base."""
    color_map = {}
    for familia, tecnologias in familias.items():
        base_color = colores_base[familia]
        tonos = generar_tonos(base_color, len(tecnologias))
        for tech, color in zip(tecnologias, tonos):
            color_map[tech] = color
    return color_map


COLOR_MAP_PWR = construir_color_map_por_familias(FAMILIAS_TEC, COLOR_BASE_FAMILIA)


# ---------------------------------------------------------------------------
# Colores por grupo de combustible (para gráficas sectoriales)
# Unión de todas las variantes del notebook (REF, RES, IND, TRA, TER, OTROS)
# ---------------------------------------------------------------------------

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
    "BAG": "#17becf",
    "DSL": "#aec7e8",
    "LPG": "#ffbb78",
    "FOL": "#98df8a",
    "AUT": "#ff9896",
    "PHEV": "#98df8a",
    "HEV": "#ff9896",
}


def asignar_grupo(nombre):
    """Mapea un nombre TECHNOLOGY_FUEL al grupo de combustible (ELC, JET, NGS, COA, etc.)."""
    if "ELC" in nombre:
        return "ELC"
    elif "JET" in nombre:
        return "JET"
    elif "LPG" in nombre:
        return "LPG"
    elif "BDL" in nombre:
        return "BDL"
    elif "WAS" in nombre:
        return "WAS"
    elif "WOO" in nombre:
        return "WOO"
    elif "BGS" in nombre:
        return "BGS"
    elif "GSL" in nombre:
        return "GSL"
    elif "DSL" in nombre:
        return "DSL"
    elif "NGS" in nombre:
        return "NGS"
    elif "BAG" in nombre:
        return "BAG"
    elif "COA" in nombre:
        return "COA"
    elif "FOL" in nombre:
        return "FOL"
    elif "APHEV" in nombre:
        return "PHEV"
    elif "AHEV" in nombre:
        return "HEV"
    elif "AUT" in nombre:
        return "AUT"
    else:
        return nombre


def generar_colores_tecnologias(df, columna="COLOR"):
    """Genera lista de colores y orden para tecnologías según grupo de combustible."""
    df["GRUPO"] = df[columna].apply(asignar_grupo)
    color_dict = {}
    orden_final = []

    for grupo in sorted(df["GRUPO"].unique()):
        subitems = sorted(df[df["GRUPO"] == grupo][columna].unique())
        base_color = COLORES_GRUPOS.get(grupo, "#999999")
        rgb = mcolors.to_rgb(base_color)
        h, l, s = rgb_to_hls(*rgb)
        n = len(subitems)

        for i, item in enumerate(subitems):
            if n <= 3:
                factor = 0.6 + 0.2 * (i / max(n - 1, 1))
                l_adj = min(max(l * factor, 0), 1)
                new_rgb = hls_to_rgb(h, l_adj, s)
            else:
                hue_shift = (i / n) * 0.15
                lightness_shift = 0.45 + 0.4 * (i / (n - 1))
                new_rgb = hls_to_rgb((h + hue_shift) % 1.0, lightness_shift, s)

            color_dict[item] = to_hex(np.clip(new_rgb, 0, 1))
            orden_final.append(item)

    return [color_dict[c] for c in orden_final], orden_final


# ---------------------------------------------------------------------------
# Variables intermedias (replicado del notebook)
# ---------------------------------------------------------------------------

def compute_intermediate_variables(inst):
    """Calcula variables intermedias post-solver: RateOfProductionByTechnology, ProductionByTechnology,
    TotalCapacityAnnual, AccumulatedNewCapacity, RateOfUseByTechnology, UseByTechnology."""
    from pyomo.environ import value

    RateOfProductionByTechnology = {}
    ProductionByTechnology = {}

    for r in inst.REGION:
        for l in inst.TIMESLICE:
            for t in inst.TECHNOLOGY:
                for f in inst.FUEL:
                    for y in inst.YEAR:
                        RateOfProductionByTechnology[r, l, t, f, y] = value(
                            sum(
                                inst.RateOfActivity[r, l, t, m, y]
                                * inst.OutputActivityRatio[r, t, f, m, y]
                                for m in inst.MODE_OF_OPERATION
                            )
                        )
                        ProductionByTechnology[r, l, t, f, y] = (
                            RateOfProductionByTechnology[r, l, t, f, y]
                            * inst.YearSplit[l, y]
                        )

    inst.RateOfProductionByTechnology = RateOfProductionByTechnology
    inst.ProductionByTechnology = ProductionByTechnology

    TotalCapacityAnnual = {}
    AccumulatedNewCapacity = {}
    for r in inst.REGION:
        for t in inst.TECHNOLOGY:
            for y in inst.YEAR:
                TotalCapacityAnnual[r, t, y] = value(
                    sum(
                        inst.NewCapacity[r, t, yy]
                        for yy in inst.YEAR
                        if ((y - yy < inst.OperationalLife[r, t]) and (y - yy >= 0))
                    )
                    + inst.ResidualCapacity[r, t, y]
                )
                AccumulatedNewCapacity[r, t, y] = value(
                    sum(
                        inst.NewCapacity[r, t, yy]
                        for yy in inst.YEAR
                        if ((y - yy < inst.OperationalLife[r, t]) and (y - yy >= 0))
                    )
                )
    inst.TotalCapacityAnnual = TotalCapacityAnnual
    inst.AccumulatedNewCapacity = AccumulatedNewCapacity

    RateOfUseByTechnologyByMode = {}
    RateOfUseByTechnology = {}
    UseByTechnology = {}
    for r in inst.REGION:
        for l in inst.TIMESLICE:
            for t in inst.TECHNOLOGY:
                for m in inst.MODE_OF_OPERATION:
                    for f in inst.FUEL:
                        for y in inst.YEAR:
                            RateOfUseByTechnologyByMode[r, l, t, m, f, y] = value(
                                inst.RateOfActivity[r, l, t, m, y]
                                * inst.InputActivityRatio[r, t, f, m, y]
                            )
                            RateOfUseByTechnology[r, l, t, f, y] = value(
                                sum(
                                    RateOfUseByTechnologyByMode[r, l, t, mm, f, y]
                                    for mm in inst.MODE_OF_OPERATION
                                )
                            )
                            UseByTechnology[r, l, t, f, y] = value(
                                RateOfUseByTechnology[r, l, t, f, y]
                                * inst.YearSplit[l, y]
                            )
    inst.RateOfUseByTechnologyByMode = RateOfUseByTechnologyByMode
    inst.RateOfUseByTechnology = RateOfUseByTechnology
    inst.UseByTechnology = UseByTechnology


# ============================================================================
# 1. graf_CAP_ELEC - Capacidad eléctrica por tecnología
# ============================================================================

def graf_CAP_ELEC(variable_name, tech_filter, UN, solver_selec):
    """Gráfica de barras: capacidad eléctrica por tecnología y año (TotalCapacityAnnual, NewCapacity, etc.).
    tech_filter: prefijo filtro (ej. PWR); UN: GW o MW."""
    if solver_selec == "highs":
        df_var = sol_variable_to_df(
            sol, variable_name, ["REGION", "TECHNOLOGY", "YEAR"]
        ).drop(columns="DUMMY")
    elif solver_selec == "glpk":
        variable_mapping = {
            "TotalCapacityAnnual": instance.TotalCapacityAnnual,
            "NewCapacity": instance.NewCapacity,
            "AccumulatedNewCapacity": instance.AccumulatedNewCapacity,
            "NumberOfNewTechnologyUnits": instance.NumberOfNewTechnologyUnits,
        }
        if variable_name not in variable_mapping:
            raise ValueError(f"Variable no válida: {variable_name}")
        variable = variable_mapping[variable_name]
        df_var = variable_to_dataframe(variable, index_names=["REGION", "TECHNOLOGY", "YEAR"])

    df_cap = df_var.copy()
    if df_cap.empty:
        print("No hay datos")
        return

    df_final = df_cap.groupby(["TECHNOLOGY", "YEAR"], as_index=False)["VALUE"].sum()
    df_final = df_final[df_final["VALUE"] > 1e-5]
    if tech_filter:
        df_final = df_final[df_final["TECHNOLOGY"].str.startswith(tech_filter)]
    if UN == "GW":
        df_final["VALUE"] /= 31.536

    fig = px.bar(
        df_final, x="YEAR", y="VALUE", color="TECHNOLOGY",
        title="Matriz Eléctrica por Tecnología - " + variable_name,
        labels={"VALUE": UN}, color_discrete_map=COLOR_MAP_PWR,
    )
    fig.update_layout(legend=dict(traceorder="normal"))
    fig.show()
    df_final.to_csv("resultados/" + "Cap_Elec" + variable_name + ".csv")


# ============================================================================
# 2. graf_Production_by_Tech_ELEC - Producción eléctrica por tecnología
# ============================================================================

def graf_Production_by_Tech_ELEC(variable_name, filtro, UN, pasos, solver_selec):
    """Gráfica de barras: generación eléctrica por tecnología (filtro PWR, etc.). pasos: 1=anual, >1=timeslices."""
    if solver_selec == "highs":
        df_var = sol_variable_to_df(
            sol, variable_name, ["REGION", "TIMESLICE", "TECHNOLOGY", "FUEL", "YEAR"]
        ).drop(columns="DUMMY")
    elif solver_selec == "glpk":
        variable_mapping = {
            "RateOfProductionByTechnology": instance.RateOfProductionByTechnology,
            "ProductionByTechnology": instance.ProductionByTechnology,
        }
        if variable_name not in variable_mapping:
            raise ValueError(f"Variable no válida: {variable_name}")
        variable = variable_mapping[variable_name]
        df_var = variable_to_dataframe(
            variable, index_names=["REGION", "TIMESLICE", "TECHNOLOGY", "FUEL", "YEAR"]
        )

    df_cap = df_var.copy()
    if df_cap.empty:
        print("No hay datos")
        return

    df_cap = df_cap[df_cap["TECHNOLOGY"].str.startswith(filtro)]
    df_cap["YEAR"] = df_cap["YEAR"].astype(int)

    if pasos == 1:
        df_cap["TIME"] = df_cap["YEAR"].astype(str)
        df_cap["TIME_NUM"] = df_cap["YEAR"]
    else:
        df_cap["BLOCK"] = df_cap["TIMESLICE"].str[1:3].astype(int)
        df_cap["TIME"] = df_cap["YEAR"].astype(str) + "_" + df_cap["TIMESLICE"]
        df_cap["TIME_NUM"] = df_cap["YEAR"] + (df_cap["BLOCK"] - 1) / df_cap["BLOCK"].max()

    df_cap["COLOR"] = df_cap["TECHNOLOGY"]

    df_final = df_cap.groupby(["COLOR", "TIME", "TIME_NUM"], as_index=False)["VALUE"].sum()
    df_final = df_final[df_final["VALUE"].abs() > 1e-5]
    if UN == "TWh":
        df_final["VALUE"] /= 3.6
    df_final = df_final.sort_values("TIME_NUM")

    fig = px.bar(
        df_final, x="TIME", y="VALUE", color="COLOR",
        title="Generación de electricidad por tecnología - " + variable_name,
        labels={"VALUE": UN}, color_discrete_map=COLOR_MAP_PWR,
    )
    fig.update_xaxes(categoryorder="array", categoryarray=df_final["TIME"])
    fig.update_layout(legend=dict(traceorder="normal"))
    fig.show()
    df_final.to_csv("resultados/" + "Prod_Elec_" + variable_name + "_" + str(pasos) + "TS" + ".csv")


# ============================================================================
# 3. graf_GAS - Oferta de gas natural
# ============================================================================

def graf_GAS(variable_name, UN, solver_selec):
    """Gráfica de barras: oferta de gas natural (tecnologías UPSREG, MINNGS). UN: Gpc o PJ."""
    if solver_selec == "highs":
        df_var = sol_variable_to_df(
            sol, variable_name, ["REGION", "TIMESLICE", "TECHNOLOGY", "FUEL", "YEAR"]
        ).drop(columns="DUMMY")
    elif solver_selec == "glpk":
        variable_mapping = {
            "ProductionByTechnology": instance.ProductionByTechnology,
        }
        if variable_name not in variable_mapping:
            raise ValueError(f"Variable no válida: {variable_name}")
        variable = variable_mapping[variable_name]
        df_var = variable_to_dataframe(
            variable, index_names=["REGION", "TIMESLICE", "TECHNOLOGY", "FUEL", "YEAR"]
        )

    df_cap = df_var.copy()
    if df_cap.empty:
        print("No hay datos")
        return

    df_cap["TIME"] = df_cap["YEAR"].astype(str)
    df_cap["COLOR"] = df_cap["TECHNOLOGY"].astype(str)

    df_final = df_cap[
        (df_cap["TECHNOLOGY"].str.startswith("UPSREG"))
        | (df_cap["TECHNOLOGY"].str.startswith("MINNGS"))
    ].copy()

    if UN == "Gpc":
        df_final["VALUE"] = df_final["VALUE"] / 1.0095581216

    fig = px.bar(
        df_final, x="TIME", y="VALUE", color="COLOR",
        title="Oferta Gas Natural", labels={"VALUE": UN},
    )
    fig.show()
    df_final.to_csv("resultados/" + "Prod_GN_" + UN + ".csv")


# ============================================================================
# 4. graf_GAS_consumo - Consumo de gas natural
# ============================================================================

def graf_GAS_consumo(variable_name, UN, solver_selec):
    """Gráfica de barras: consumo de gas natural (tecnologías que contienen NGS)."""
    if solver_selec == "highs":
        df_var = sol_variable_to_df(
            sol, variable_name, ["REGION", "TIMESLICE", "TECHNOLOGY", "FUEL", "YEAR"]
        ).drop(columns="DUMMY")
    elif solver_selec == "glpk":
        variable_mapping = {
            "UseByTechnology": instance.UseByTechnology,
        }
        if variable_name not in variable_mapping:
            raise ValueError(f"Variable no válida: {variable_name}")
        variable = variable_mapping[variable_name]
        df_var = variable_to_dataframe(
            variable, index_names=["REGION", "TIMESLICE", "TECHNOLOGY", "FUEL", "YEAR"]
        )

    df_cap = df_var.copy()
    if df_cap.empty:
        print("No hay datos")
        return

    df_cap["TIME"] = df_cap["YEAR"].astype(str)
    df_cap["COLOR"] = df_cap["TECHNOLOGY"].astype(str)

    df_final = df_cap[df_cap["TECHNOLOGY"].str.contains("NGS")].copy()

    if UN == "Gpc":
        df_final["VALUE"] = df_final["VALUE"] / 1.0095581216

    fig = px.bar(
        df_final, x="TIME", y="VALUE", color="COLOR",
        title="Consumo Gas Natural", labels={"VALUE": UN},
    )
    fig.show()
    df_final.to_csv("resultados/" + "Consumo_GN_" + UN + ".csv")


# ============================================================================
# Helper: _load_5d_df (patrón común a gráficas sectoriales)
# ============================================================================

def _load_5d_df(variable_name, solver_selec):
    """Carga un DataFrame de 5 dimensiones (REGION,TIMESLICE,TECHNOLOGY,FUEL,YEAR).
    Patrón común para gráficas sectoriales (ProductionByTechnology o UseByTechnology)."""
    if solver_selec == "highs":
        df_var = sol_variable_to_df(
            sol, variable_name, ["REGION", "TIMESLICE", "TECHNOLOGY", "FUEL", "YEAR"]
        ).drop(columns="DUMMY")
    elif solver_selec == "glpk":
        variable_mapping = {
            "ProductionByTechnology": instance.ProductionByTechnology,
            "UseByTechnology": instance.UseByTechnology,
        }
        if variable_name not in variable_mapping:
            raise ValueError(f"Variable no válida: {variable_name}")
        variable = variable_mapping[variable_name]
        df_var = variable_to_dataframe(
            variable, index_names=["REGION", "TIMESLICE", "TECHNOLOGY", "FUEL", "YEAR"]
        )
    else:
        raise ValueError(f"Solver no válido: {solver_selec}")
    return df_var.copy()


# ============================================================================
# 5. graf_demand_REF_combustible_TOTAL - Refinerías: demanda total por combustible
# ============================================================================

def graf_demand_REF_combustible_TOTAL(variable_name, UN, pasos, solver_selec):
    """Gráfica de barras: sector refinerías (UPSREF) consumiendo por grupo de combustible."""
    df_cap = _load_5d_df(variable_name, solver_selec)
    if df_cap.empty:
        print(f"No hay datos para la variable {variable_name}")
        return

    df_cap = df_cap[df_cap["TECHNOLOGY"].str.startswith("UPSREF")]

    if pasos == 1:
        df_cap["TIME"] = df_cap["YEAR"].astype(str)
    else:
        df_cap["TIME"] = df_cap["YEAR"].astype(str) + "_" + df_cap["TIMESLICE"]

    df_cap["COLOR"] = df_cap["TECHNOLOGY"] + "_" + df_cap["FUEL"]
    df_cap["GROUP"] = df_cap["COLOR"].apply(asignar_grupo)

    df_final = df_cap.groupby(["GROUP", "TIME"], as_index=False)["VALUE"].sum()
    df_final = df_final.rename(columns={"GROUP": "COLOR"})
    df_final = df_final[df_final.groupby("COLOR")["VALUE"].transform("sum") > 1e-5]

    if UN == "TWh":
        df_final["VALUE"] /= 3.6

    grupos_presentes = df_final["COLOR"].unique()
    colores_final = [COLORES_GRUPOS.get(grupo, "#333333") for grupo in grupos_presentes]

    fig = px.bar(
        df_final, x="TIME", y="VALUE", color="COLOR",
        title="REFINERIAS", labels={"VALUE": UN},
        color_discrete_sequence=colores_final,
    )
    fig.show()
    df_final.to_csv("resultados/" + "REFINERIAS_" + variable_name + "_" + UN + ".csv")


# ============================================================================
# 6. graf_demand_REF_combustible_IMPORT (notebook exact)
# ============================================================================

def graf_demand_REF_combustible_IMPORT(variable_name, UN, pasos, solver_selec):
    df_cap = _load_5d_df(variable_name, solver_selec)
    if df_cap.empty:
        print(f"No hay datos para la variable {variable_name}")
        return

    df_cap = df_cap[
        df_cap["TECHNOLOGY"].str.startswith("UPSREF")
        | df_cap["TECHNOLOGY"].str.startswith("IMPLPG")
        | df_cap["TECHNOLOGY"].str.startswith("IMPDSL")
        | df_cap["TECHNOLOGY"].str.startswith("IMPGSL")
    ]

    if pasos == 1:
        df_cap["TIME"] = df_cap["YEAR"].astype(str)
    else:
        df_cap["TIME"] = df_cap["YEAR"].astype(str) + "_" + df_cap["TIMESLICE"]

    df_cap["COLOR"] = df_cap["TECHNOLOGY"]

    if UN == "TWh":
        df_cap["VALUE"] /= 3.6

    fig = px.bar(
        df_cap, x="TIME", y="VALUE", title="REFINERIAS",
        labels={"VALUE": UN}, color="COLOR",
    )
    fig.show()
    df_cap.to_csv("resultados/" + "REF+IMP_" + variable_name + "_" + UN + ".csv")


# ============================================================================
# 7. graf_demand_RES_combustible_TOTAL (notebook exact)
# ============================================================================

def graf_demand_RES_combustible_TOTAL(variable_name, UN, pasos, solver_selec):
    df_cap = _load_5d_df(variable_name, solver_selec)
    if df_cap.empty:
        print(f"No hay datos para la variable {variable_name}")
        return

    df_cap = df_cap[df_cap["TECHNOLOGY"].str.startswith("DEMRES")]

    if pasos == 1:
        df_cap["TIME"] = df_cap["YEAR"].astype(str)
    else:
        df_cap["TIME"] = df_cap["YEAR"].astype(str) + "_" + df_cap["TIMESLICE"]

    df_cap["COLOR"] = df_cap["TECHNOLOGY"] + "_" + df_cap["FUEL"]
    df_cap["GROUP"] = df_cap["COLOR"].apply(asignar_grupo)

    df_final = df_cap.groupby(["GROUP", "TIME"], as_index=False)["VALUE"].sum()
    df_final = df_final.rename(columns={"GROUP": "COLOR"})
    df_final = df_final[df_final.groupby("COLOR")["VALUE"].transform("sum") > 1e-5]

    if UN == "TWh":
        df_final["VALUE"] /= 3.6

    grupos_presentes = df_final["COLOR"].unique()
    colores_final = [COLORES_GRUPOS.get(grupo, "#333333") for grupo in grupos_presentes]

    fig = px.bar(
        df_final, x="TIME", y="VALUE", color="COLOR",
        title="SECTOR RESIDENCIAL - Consumo total por combustible", labels={"VALUE": UN},
        color_discrete_sequence=colores_final,
    )
    fig.show()
    df_final.to_csv("resultados/" + "RESIDENCIAL_TOTAL_" + variable_name + "_" + UN + ".csv")


# ============================================================================
# 8. graf_demand_RES_combustible (notebook exact)
# ============================================================================

def graf_demand_RES_combustible(variable_name, UN, pasos, filtro, solver_selec):
    df_cap = _load_5d_df(variable_name, solver_selec)
    if df_cap.empty:
        print(f"No hay datos para la variable {variable_name}")
        return

    df_cap = df_cap[
        df_cap["TECHNOLOGY"].str.startswith("DEMRES")
        & df_cap["TECHNOLOGY"].str.contains(filtro)
    ]

    if pasos == 1:
        df_cap["TIME"] = df_cap["YEAR"].astype(str)
    else:
        df_cap["TIME"] = df_cap["YEAR"].astype(str) + "_" + df_cap["TIMESLICE"]

    df_cap["COLOR"] = df_cap["TECHNOLOGY"] + "_" + df_cap["FUEL"]
    df_cap["GROUP"] = df_cap["COLOR"].apply(asignar_grupo)

    df_final = df_cap.groupby(["GROUP", "TIME"], as_index=False)["VALUE"].sum()
    df_final = df_final.rename(columns={"GROUP": "COLOR"})
    df_final = df_final[df_final.groupby("COLOR")["VALUE"].transform("sum") > 1e-5]

    if UN == "TWh":
        df_final["VALUE"] /= 3.6

    grupos_presentes = df_final["COLOR"].unique()
    colores_final = [COLORES_GRUPOS.get(grupo, "#333333") for grupo in grupos_presentes]

    fig = px.bar(
        df_final, x="TIME", y="VALUE", color="COLOR",
        title="SECTOR RESIDENCIAL - " + filtro, labels={"VALUE": UN},
        color_discrete_sequence=colores_final,
    )
    fig.show()
    df_final.to_csv(
        "resultados/" + "RESIDENCIAL_" + filtro + "_" + variable_name + "_" + UN + ".csv"
    )


# ============================================================================
# 9. graf_demand_RES_TEC (notebook exact)
# ============================================================================

def graf_demand_RES_TEC(variable_name, UN, pasos, filtro, LOC, solver_selec):
    df_cap = _load_5d_df(variable_name, solver_selec)
    if df_cap.empty:
        print(f"No hay datos para la variable {variable_name}")
        return

    df_cap = df_cap[
        df_cap["TECHNOLOGY"].str.startswith("DEMRES")
        & df_cap["TECHNOLOGY"].str.contains(filtro)
    ]

    if LOC == "URBANO":
        df_cap = df_cap[
            ~df_cap["TECHNOLOGY"].str.contains("RUR")
            & ~df_cap["TECHNOLOGY"].str.contains("ZNI")
        ]
    elif LOC == "RURAL":
        df_cap = df_cap[df_cap["TECHNOLOGY"].str.contains("RUR")]
    elif LOC == "ZNI":
        df_cap = df_cap[df_cap["TECHNOLOGY"].str.contains("ZNI")]

    if pasos == 1:
        df_cap["TIME"] = df_cap["YEAR"].astype(str)
    else:
        df_cap["TIME"] = df_cap["YEAR"].astype(str) + "_" + df_cap["TIMESLICE"]

    df_cap["COLOR"] = df_cap["TECHNOLOGY"]

    df_final = df_cap.groupby(["COLOR", "TIME"], as_index=False)["VALUE"].sum()
    df_final = df_final[df_final.groupby("COLOR")["VALUE"].transform("sum") > 1e-5]

    if UN == "TWh":
        df_final["VALUE"] /= 3.6

    colores_final, orden_color = generar_colores_tecnologias(df_final, "COLOR")

    fig = px.bar(
        df_final, x="TIME", y="VALUE", color="COLOR",
        title="SECTOR RESIDENCIAL - " + filtro + " - " + LOC,
        labels={"VALUE": UN},
        color_discrete_sequence=colores_final,
        category_orders={"COLOR": orden_color},
    )
    fig.show()
    df_final.to_csv(
        "resultados/" + "RES_TEC_" + filtro + "_" + LOC + "_" + variable_name + "_" + UN + ".csv"
    )


# ============================================================================
# 10. graf_demand_IND_combustible_TOTAL (notebook exact)
# ============================================================================

def graf_demand_IND_combustible_TOTAL(variable_name, UN, pasos, solver_selec):
    df_cap = _load_5d_df(variable_name, solver_selec)
    if df_cap.empty:
        print(f"No hay datos para la variable {variable_name}")
        return

    df_cap = df_cap[df_cap["TECHNOLOGY"].str.startswith("DEMIND")]

    if pasos == 1:
        df_cap["TIME"] = df_cap["YEAR"].astype(str)
    else:
        df_cap["TIME"] = df_cap["YEAR"].astype(str) + "_" + df_cap["TIMESLICE"]

    df_cap["COLOR"] = df_cap["TECHNOLOGY"] + "_" + df_cap["FUEL"]
    df_cap["GROUP"] = df_cap["COLOR"].apply(asignar_grupo)

    df_final = df_cap.groupby(["GROUP", "TIME"], as_index=False)["VALUE"].sum()
    df_final = df_final.rename(columns={"GROUP": "COLOR"})
    df_final = df_final[df_final.groupby("COLOR")["VALUE"].transform("sum") > 1e-5]

    if UN == "TWh":
        df_final["VALUE"] /= 3.6

    grupos_presentes = df_final["COLOR"].unique()
    colores_final = [COLORES_GRUPOS.get(grupo, "#333333") for grupo in grupos_presentes]

    fig = px.bar(
        df_final, x="TIME", y="VALUE", color="COLOR",
        title="SECTOR INDUSTRIAL - Consumo total por combustible", labels={"VALUE": UN},
        color_discrete_sequence=colores_final,
    )
    fig.show()
    df_final.to_csv("resultados/" + "INDUSTRIAL_TOTAL_" + variable_name + "_" + UN + ".csv")


# ============================================================================
# 11. graf_demand_ind_combustible (notebook exact)
# ============================================================================

def graf_demand_ind_combustible(variable_name, UN, pasos, filtro, solver_selec):
    df_cap = _load_5d_df(variable_name, solver_selec)
    if df_cap.empty:
        print(f"No hay datos para la variable {variable_name}")
        return

    df_cap = df_cap[
        df_cap["TECHNOLOGY"].str.startswith("DEMIND")
        & df_cap["TECHNOLOGY"].str.contains(filtro)
    ]

    if pasos == 1:
        df_cap["TIME"] = df_cap["YEAR"].astype(str)
    else:
        df_cap["TIME"] = df_cap["YEAR"].astype(str) + "_" + df_cap["TIMESLICE"]

    df_cap["COLOR"] = df_cap["TECHNOLOGY"] + "_" + df_cap["FUEL"]
    df_cap["GROUP"] = df_cap["COLOR"].apply(asignar_grupo)

    df_final = df_cap.groupby(["GROUP", "TIME"], as_index=False)["VALUE"].sum()
    df_final = df_final.rename(columns={"GROUP": "COLOR"})
    df_final = df_final[df_final.groupby("COLOR")["VALUE"].transform("sum") > 1e-5]

    if UN == "TWh":
        df_final["VALUE"] /= 3.6

    grupos_presentes = df_final["COLOR"].unique()
    colores_final = [COLORES_GRUPOS.get(grupo, "#333333") for grupo in grupos_presentes]

    fig = px.bar(
        df_final, x="TIME", y="VALUE", color="COLOR",
        title="SECTOR INDUSTRIAL - " + filtro, labels={"VALUE": UN},
        color_discrete_sequence=colores_final,
    )
    fig.show()
    df_final.to_csv(
        "resultados/" + "INDUSTRIAL_" + filtro + "_" + variable_name + "_" + UN + ".csv"
    )


# ============================================================================
# 12. graf_demand_TRA_combustible_TOTAL (notebook exact)
# ============================================================================

def graf_demand_TRA_combustible_TOTAL(variable_name, UN, pasos, solver_selec):
    df_cap = _load_5d_df(variable_name, solver_selec)
    if df_cap.empty:
        print(f"No hay datos para la variable {variable_name}")
        return

    df_cap = df_cap[df_cap["TECHNOLOGY"].str.startswith("DEMTRA")]

    if pasos == 1:
        df_cap["TIME"] = df_cap["YEAR"].astype(str)
    else:
        df_cap["TIME"] = df_cap["YEAR"].astype(str) + "_" + df_cap["TIMESLICE"]

    df_cap["COLOR"] = df_cap["TECHNOLOGY"] + "_" + df_cap["FUEL"]
    df_cap["GROUP"] = df_cap["COLOR"].apply(asignar_grupo)

    df_final = df_cap.groupby(["GROUP", "TIME"], as_index=False)["VALUE"].sum()
    df_final = df_final.rename(columns={"GROUP": "COLOR"})
    df_final = df_final[df_final.groupby("COLOR")["VALUE"].transform("sum") > 1e-5]

    if UN == "TWh":
        df_final["VALUE"] /= 3.6

    grupos_presentes = df_final["COLOR"].unique()
    colores_final = [COLORES_GRUPOS.get(grupo, "#333333") for grupo in grupos_presentes]

    fig = px.bar(
        df_final, x="TIME", y="VALUE", color="COLOR",
        title="SECTOR TRANSPORTE - Consumo por combustible - " + variable_name,
        labels={"VALUE": UN}, color_discrete_sequence=colores_final,
    )
    fig.show()
    df_final.to_csv("resultados/" + "TRANSPORTE TOTAL_" + variable_name + "_" + UN + ".csv")


# ============================================================================
# 13. graf_demand_TRA_combustible (notebook exact)
# ============================================================================

def graf_demand_TRA_combustible(variable_name, UN, pasos, filtro, solver_selec):
    df_cap = _load_5d_df(variable_name, solver_selec)
    if df_cap.empty:
        print(f"No hay datos para la variable {variable_name}")
        return

    df_cap = df_cap[
        df_cap["TECHNOLOGY"].str.startswith("DEMTRA")
        & df_cap["TECHNOLOGY"].str.contains(filtro)
    ]

    if pasos == 1:
        df_cap["TIME"] = df_cap["YEAR"].astype(str)
    else:
        df_cap["TIME"] = df_cap["YEAR"].astype(str) + "_" + df_cap["TIMESLICE"]

    df_cap["COLOR"] = df_cap["TECHNOLOGY"] + "_" + df_cap["FUEL"]
    df_cap["GROUP"] = df_cap["COLOR"].apply(asignar_grupo)

    df_final = df_cap.groupby(["GROUP", "TIME"], as_index=False)["VALUE"].sum()
    df_final = df_final.rename(columns={"GROUP": "COLOR"})
    df_final = df_final[df_final.groupby("COLOR")["VALUE"].transform("sum") > 1e-5]

    if UN == "TWh":
        df_final["VALUE"] /= 3.6

    grupos_presentes = df_final["COLOR"].unique()
    colores_final = [COLORES_GRUPOS.get(grupo, "#333333") for grupo in grupos_presentes]

    fig = px.bar(
        df_final, x="TIME", y="VALUE", color="COLOR",
        title="SECTOR TRANSPORTE - Consumo por combustible- " + filtro,
        labels={"VALUE": UN}, color_discrete_sequence=colores_final,
    )
    fig.show()
    df_final.to_csv(
        "resultados/" + "TRANSPORTE_" + filtro + "_" + variable_name + "_" + UN + ".csv"
    )


# ============================================================================
# 14. graf_demand_TER_combustible_TOTAL (notebook exact)
# ============================================================================

def graf_demand_TER_combustible_TOTAL(variable_name, UN, pasos, solver_selec):
    df_cap = _load_5d_df(variable_name, solver_selec)
    if df_cap.empty:
        print(f"No hay datos para la variable {variable_name}")
        return

    df_cap = df_cap[df_cap["TECHNOLOGY"].str.startswith("DEMTER")]

    if pasos == 1:
        df_cap["TIME"] = df_cap["YEAR"].astype(str)
    else:
        df_cap["TIME"] = df_cap["YEAR"].astype(str) + "_" + df_cap["TIMESLICE"]

    df_cap["COLOR"] = df_cap["TECHNOLOGY"] + "_" + df_cap["FUEL"]
    df_cap["GROUP"] = df_cap["COLOR"].apply(asignar_grupo)

    df_final = df_cap.groupby(["GROUP", "TIME"], as_index=False)["VALUE"].sum()
    df_final = df_final.rename(columns={"GROUP": "COLOR"})
    df_final = df_final[df_final.groupby("COLOR")["VALUE"].transform("sum") > 1e-5]

    if UN == "TWh":
        df_final["VALUE"] /= 3.6

    grupos_presentes = df_final["COLOR"].unique()
    colores_final = [COLORES_GRUPOS.get(grupo, "#333333") for grupo in grupos_presentes]

    fig = px.bar(
        df_final, x="TIME", y="VALUE", color="COLOR",
        title="SECTOR TERCIARIO - " + variable_name, labels={"VALUE": UN},
        color_discrete_sequence=colores_final,
    )
    fig.show()
    df_final.to_csv("resultados/" + "TERCIARIO_TOTAL_" + variable_name + "_" + UN + ".csv")


# ============================================================================
# 15. graf_demand_OTROS_combustible_TOTAL (notebook exact)
# ============================================================================

def graf_demand_OTROS_combustible_TOTAL(variable_name, UN, pasos, otro, solver_selec):
    df_cap = _load_5d_df(variable_name, solver_selec)
    if df_cap.empty:
        print(f"No hay datos para la variable {variable_name}")
        return

    df_cap = df_cap[df_cap["TECHNOLOGY"].str.startswith(otro)]

    if pasos == 1:
        df_cap["TIME"] = df_cap["YEAR"].astype(str)
    else:
        df_cap["TIME"] = df_cap["YEAR"].astype(str) + "_" + df_cap["TIMESLICE"]

    df_cap["COLOR"] = df_cap["TECHNOLOGY"] + "_" + df_cap["FUEL"]
    df_cap["GROUP"] = df_cap["COLOR"].apply(asignar_grupo)

    df_final = df_cap.groupby(["GROUP", "TIME"], as_index=False)["VALUE"].sum()
    df_final = df_final.rename(columns={"GROUP": "COLOR"})
    df_final = df_final[df_final.groupby("COLOR")["VALUE"].transform("sum") > 1e-5]

    if UN == "TWh":
        df_final["VALUE"] /= 3.6

    grupos_presentes = df_final["COLOR"].unique()
    colores_final = [COLORES_GRUPOS.get(grupo, "#333333") for grupo in grupos_presentes]

    if otro == "DEMCOQ":
        titulo = "Coquerias - Consumo por combustible - Energía final"
    elif otro == "DEMAGF":
        titulo = "Agricultura y Pesca - Consumo por combustible - Energía final"
    else:
        titulo = f"OTROS ({otro}) - " + variable_name

    fig = px.bar(
        df_final, x="TIME", y="VALUE", color="COLOR",
        title=titulo, labels={"VALUE": UN},
        color_discrete_sequence=colores_final,
    )
    fig.show()
    df_final.to_csv("resultados/" + "OTROS_" + variable_name + "_" + UN + ".csv")


# ============================================================================
# 16. graf_emissions - Emisiones anuales por tecnología
# ============================================================================

def graf_emissions(variable_name, solver_selec):
    """Gráfica de barras: emisiones anuales por tecnología (AnnualTechnologyEmission, Mt CO2e)."""
    if solver_selec == "highs":
        df_var = sol_variable_to_df(
            sol, variable_name, ["REGION", "TECHNOLOGY", "EMISSION", "YEAR"]
        ).drop(columns="DUMMY")
    elif solver_selec == "glpk":
        variable_mapping = {
            "AnnualTechnologyEmission": instance.AnnualTechnologyEmission,
            "AnnualTechnologyEmissionPenaltyByEmission": instance.AnnualTechnologyEmissionPenaltyByEmission,
        }
        if variable_name not in variable_mapping:
            raise ValueError(f"Variable no válida: {variable_name}")
        variable = variable_mapping[variable_name]
        df_var = variable_to_dataframe(
            variable, index_names=["REGION", "TECHNOLOGY", "EMISSION", "YEAR"]
        )

    df_cap = df_var.copy()

    df_final = df_cap[df_cap["VALUE"] > 1e-5]

    fig = px.bar(
        df_final, x="YEAR", y="VALUE", color="TECHNOLOGY",
        title=variable_name, labels={"VALUE": "Mt CO2e"},
    )
    fig.show()
    df_final.to_csv("resultados/" + "EMISIONES_" + variable_name + ".csv")


# ============================================================================
# 17. graf_CAP_storage - Capacidad de almacenamiento
# ============================================================================

def graf_CAP_storage(variable_name, solver_selec):
    """Gráfica de área y barras: capacidad de almacenamiento (StorageUpperLimit) por año."""
    if solver_selec == "highs":
        df_var = sol_variable_to_df(
            sol, variable_name, ["REGION", "STORAGE", "YEAR"]
        ).drop(columns="DUMMY")
    elif solver_selec == "glpk":
        variable_mapping = {
            "StorageUpperLimit": instance.StorageUpperLimit,
        }
        if variable_name not in variable_mapping:
            raise ValueError(f"Variable no válida: {variable_name}")
        variable = variable_mapping[variable_name]
        df_var = variable_to_dataframe(
            variable, index_names=["REGION", "STORAGE", "YEAR"]
        )

    df_cap = df_var.copy()

    df_final = df_cap.groupby(["STORAGE", "YEAR"]).sum().reset_index()
    df_final = df_final[df_final.groupby("STORAGE")["VALUE"].transform("sum") > 1e-5]

    fig = px.area(df_final, x="YEAR", y="VALUE", color="STORAGE", title=variable_name)
    fig.show()

    fig = px.bar(
        df_final, x="YEAR", y="VALUE", color="STORAGE",
        title=variable_name, labels={"VALUE": "PJ"},
    )
    fig.show()


# ============================================================================
# 18. graf_Op_Storage - Operación de almacenamiento
# ============================================================================

def graf_Op_Storage(variable_name, solver_selec):
    """Gráfica de área: operación de almacenamiento (NetCharge, RateOfCharge/Discharge) por tiempo."""
    if solver_selec == "highs":
        df_var = sol_variable_to_df(
            sol, variable_name,
            ["REGION", "STORAGE", "SEASON", "DAYTYPE", "DAILYTIMEBRACKET", "YEAR"],
        ).drop(columns="DUMMY")
    elif solver_selec == "glpk":
        variable_mapping = {
            "NetChargeWithinYear": instance.NetChargeWithinYear,
            "NetChargeWithinDay": instance.NetChargeWithinDay,
            "RateOfStorageCharge": instance.RateOfStorageCharge,
            "RateOfStorageDischarge": instance.RateOfStorageDischarge,
        }
        if variable_name not in variable_mapping:
            raise ValueError(f"Variable no válida: {variable_name}")
        variable = variable_mapping[variable_name]
        df_var = variable_to_dataframe(
            variable,
            index_names=["REGION", "STORAGE", "SEASON", "DAYTYPE", "DAILYTIMEBRACKET", "YEAR"],
        )

    df_cap = df_var.copy()

    df_cap["TIME"] = (
        df_cap["YEAR"].astype(str) + "_" + df_cap["DAILYTIMEBRACKET"].astype(str)
    )
    df_cap = df_cap.sort_values(by="TIME", ascending=True)

    df_final = df_cap

    fig = px.area(df_final, x="TIME", y="VALUE", color="STORAGE", title=variable_name)
    fig.show()


# ============================================================================
# 19. graf_Op_Storage_SOC - Estado de carga de almacenamiento
# ============================================================================

def graf_Op_Storage_SOC(variable_name, solver_selec):
    """Gráfica de área: estado de carga (StorageLevel, StorageUpperLimit, etc.) por año."""
    if solver_selec == "highs":
        df_var = sol_variable_to_df(
            sol, variable_name, ["REGION", "STORAGE", "YEAR"]
        ).drop(columns="DUMMY")
    elif solver_selec == "glpk":
        variable_mapping = {
            "StorageLevelYearStart": instance.StorageLevelYearStart,
            "StorageLevelYearFinish": instance.StorageLevelYearFinish,
            "StorageLowerLimit": instance.StorageLowerLimit,
            "StorageUpperLimit": instance.StorageUpperLimit,
            "SalvageValueStorage": instance.SalvageValueStorage,
            "DiscountedSalvageValueStorage": instance.DiscountedSalvageValueStorage,
            "TotalDiscountedStorageCost": instance.TotalDiscountedStorageCost,
            "NewStorageCapacity": instance.NewStorageCapacity,
            "CapitalInvestmentStorage": instance.CapitalInvestmentStorage,
            "AccumulatedNewStorageCapacity": instance.AccumulatedNewStorageCapacity,
        }
        if variable_name not in variable_mapping:
            raise ValueError(f"Variable no válida: {variable_name}")
        variable = variable_mapping[variable_name]
        df_var = variable_to_dataframe(
            variable, index_names=["REGION", "STORAGE", "YEAR"]
        )

    df_cap = df_var.copy()

    df_final = df_cap

    fig = px.area(df_final, x="YEAR", y="VALUE", color="STORAGE", title=variable_name)
    fig.show()


# ---------------------------------------------------------------------------
# Carga de resultado JSON (backend/tmp/*.json) para las gráficas
# ---------------------------------------------------------------------------

def cargar_resultado_json(ruta_json):
    """Carga un JSON de resultado de simulación (backend/tmp/*.json) y devuelve
    (df_new_capacity, df_dispatch) para usar en graf_CAP_ELEC y graf_Production_by_Tech_ELEC."""
    import json

    with open(ruta_json, encoding="utf-8") as f:
        data = json.load(f)

    nc = data.get("new_capacity", [])
    df_cap = pd.DataFrame([
        {
            "REGION": f"R{item['region_id']}",
            "TECHNOLOGY": item["technology_name"],
            "YEAR": item["year"],
            "VALUE": float(item["new_capacity"]),
        }
        for item in nc
    ])

    disp = data.get("dispatch", [])
    df_disp = pd.DataFrame([
        {
            "REGION": f"R{item['region_id']}",
            "TIMESLICE": "S1",
            "TECHNOLOGY": item["technology_name"],
            "FUEL": item.get("fuel_name") or "",
            "YEAR": item["year"],
            "VALUE": float(item["dispatch"]),
        }
        for item in disp
    ])

    return df_cap, df_disp
