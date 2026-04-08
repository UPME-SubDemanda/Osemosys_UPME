"""Servicio para integrar multiples archivos SAND en memoria.

Adapta la logica de referencia de `integrate_multi_sand.py` para uso en API:
- Entrada por bytes (UploadFile)
- Salida como bytes de Excel + resumen estructurado
"""

from __future__ import annotations

from collections import defaultdict
from io import BytesIO
from pathlib import Path
import time
import traceback

import numpy as np
import pandas as pd

from app.services.integrate_sand_log import (
    build_fatal_error_log,
    build_integration_sand_log,
    extract_contribution_with_combinaciones,
)
from app.simulation.core.mode_of_operation_normalize import normalize_mode_of_operation_series


KEY_COLS = [
    "Parameter",
    "REGION",
    "TECHNOLOGY",
    "EMISSION",
    "MODE_OF_OPERATION",
    "FUEL",
    "TIMESLICE",
    "STORAGE",
    "REGION2",
]

VALUE_COLS = ["Time indipendent variables"] + [str(y) for y in range(2022, 2056)]
RTOL = 1e-6


def _canonical_year_column_name(name: object) -> str | None:
    """Si `name` representa un año 2022-2055, devuelve la cadena canónica; si no, None."""
    y: int | None = None
    if isinstance(name, bool):
        return None
    if isinstance(name, (int, np.integer)):
        y = int(name)
    elif isinstance(name, float):
        if not np.isfinite(name):
            return None
        r = round(name)
        if abs(name - r) > 1e-9:
            return None
        y = int(r)
    elif isinstance(name, str):
        s = name.strip()
        if len(s) == 4 and s.isdigit():
            y = int(s)
    if y is None or y not in range(2022, 2056):
        return None
    return str(y)


def _normalize_value_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Unifica encabezados de año: Excel a veces guarda años como número (2022) y pandas los usa como int."""
    rename: dict[object, str] = {}
    drop_cols: list[object] = []

    for c in df.columns:
        target = _canonical_year_column_name(c)
        if target is None:
            continue
        if isinstance(c, str) and c.strip() == target:
            continue
        if target in df.columns and c != target:
            if isinstance(c, (int, float, np.integer)) and not isinstance(c, bool):
                drop_cols.append(c)
            continue
        rename[c] = target

    out = df.drop(columns=drop_cols, errors="ignore")
    if rename:
        out = out.rename(columns=rename)
    return out
_SENTINEL = -999999.123456789
ALLOWED_EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xls", ".xlsb", ".xltx", ".xltm"}


def _is_allowed_excel(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXCEL_EXTENSIONS


def _clean_csv_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _read_parameters_from_bytes(content: bytes) -> pd.DataFrame:
    df = pd.read_excel(BytesIO(content), sheet_name="Parameters", engine="calamine")
    df = _normalize_value_column_names(df)

    for col in KEY_COLS:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

    if "MODE_OF_OPERATION" in df.columns:
        df["MODE_OF_OPERATION"] = normalize_mode_of_operation_series(df["MODE_OF_OPERATION"])

    for col in VALUE_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.dropna(how="all").reset_index(drop=True)


def _detect_duplicates(df: pd.DataFrame, filename: str) -> list[str]:
    """Detecta duplicados por KEY_COLS y retorna mensajes legibles."""
    key_cols = [c for c in KEY_COLS if c in df.columns]
    if not key_cols:
        return [f"{filename}: no se encontraron columnas clave para validar duplicados."]
    dupes = df[df.duplicated(subset=key_cols, keep=False)]
    if dupes.empty:
        return []
    messages: list[str] = []
    for keys, grp in dupes.groupby(key_cols):
        key_tuple = keys if isinstance(keys, tuple) else (keys,)
        key_desc = ", ".join(f"{k}={v}" for k, v in zip(key_cols, key_tuple))
        excel_rows = (grp.index + 2).tolist()
        messages.append(
            f"{filename}: {len(grp)} duplicados para [{key_desc}] en filas Excel {excel_rows}"
        )
    return messages


def _detect_duplicates_detail(df: pd.DataFrame, filename: str) -> pd.DataFrame:
    """Filas con claves KEY_COLS duplicadas dentro de un archivo (como la referencia)."""
    key_cols = [c for c in KEY_COLS if c in df.columns]
    if not key_cols:
        return pd.DataFrame()
    dupes = df[df.duplicated(subset=key_cols, keep=False)]
    if dupes.empty:
        return pd.DataFrame()
    records: list[dict] = []
    for keys, grp in dupes.groupby(key_cols):
        key_tuple = keys if isinstance(keys, tuple) else (keys,)
        row = dict(zip(key_cols, key_tuple))
        row["filas_excel"] = ",".join(str(x) for x in (grp.index + 2).tolist())
        row["archivo"] = filename
        row["n_duplicados"] = int(len(grp))
        records.append(row)
    return pd.DataFrame(records)


def _detect_diffs(df_base: pd.DataFrame, df_new: pd.DataFrame) -> pd.DataFrame:
    val_cols = [c for c in VALUE_COLS if c in df_base.columns]
    base_idx = df_base.set_index(KEY_COLS)
    new_idx = df_new.set_index(KEY_COLS)

    idx_base = set(base_idx.index)
    idx_new = set(new_idx.index)
    diffs: list[dict] = []

    for idx in idx_base - idx_new:
        key = dict(zip(KEY_COLS, idx if isinstance(idx, tuple) else (idx,)))
        diffs.append(
            {
                **key,
                "tipo_cambio": "ELIMINADA",
                "columna": "—",
                "valor_base": "—",
                "valor_nuevo": "—",
            }
        )

    for idx in idx_new - idx_base:
        key = dict(zip(KEY_COLS, idx if isinstance(idx, tuple) else (idx,)))
        diffs.append(
            {
                **key,
                "tipo_cambio": "NUEVA",
                "columna": "—",
                "valor_base": "—",
                "valor_nuevo": "—",
            }
        )

    common = list(idx_base & idx_new)
    if common and val_cols:
        base_vals = base_idx.loc[common, val_cols]
        new_vals = new_idx.loc[common, val_cols]

        base_matrix = base_vals.values.astype(float)
        new_matrix = new_vals.values.astype(float)
        rows, cols = np.where(~np.isclose(base_matrix, new_matrix, rtol=RTOL, atol=0, equal_nan=True))

        for row_i, col_i in zip(rows, cols):
            idx = common[row_i]
            key = dict(zip(KEY_COLS, idx if isinstance(idx, tuple) else (idx,)))
            diffs.append(
                {
                    **key,
                    "tipo_cambio": "MODIFICADA",
                    "columna": val_cols[col_i],
                    "valor_base": base_matrix[row_i, col_i],
                    "valor_nuevo": new_matrix[row_i, col_i],
                }
            )

    if diffs:
        return pd.DataFrame(diffs)
    return pd.DataFrame(columns=KEY_COLS + ["tipo_cambio", "columna", "valor_base", "valor_nuevo"])


def _detect_conflicts(
    df_base: pd.DataFrame,
    names_new: list[str],
    dfs_new: list[pd.DataFrame],
    diffs_vs_base: list[pd.DataFrame],
) -> list[dict]:
    val_cols = [c for c in VALUE_COLS if c in df_base.columns]

    mod_map: dict[tuple, dict[str, float]] = defaultdict(dict)
    for name, diffs in zip(names_new, diffs_vs_base):
        mod = diffs[diffs["tipo_cambio"] == "MODIFICADA"]
        for _, row in mod.iterrows():
            cell_key = tuple(row[k] for k in KEY_COLS) + (row["columna"],)
            mod_map[cell_key][name] = row["valor_nuevo"]

    new_map: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for name, diffs, df_new in zip(names_new, diffs_vs_base, dfs_new):
        nuevas = diffs[diffs["tipo_cambio"] == "NUEVA"]
        if nuevas.empty:
            continue
        df_new_idx = df_new.set_index(KEY_COLS)
        for _, row in nuevas.iterrows():
            row_key = tuple(row[k] for k in KEY_COLS)
            if row_key in df_new_idx.index:
                new_map[row_key][name] = df_new_idx.loc[row_key, val_cols].to_dict()

    conflicts: list[dict] = []

    for cell_key, file_values in mod_map.items():
        if len(file_values) < 2:
            continue
        values = list(file_values.values())
        has_conflict = any(
            not np.isclose(v1, v2, rtol=RTOL, atol=0, equal_nan=True)
            for i, v1 in enumerate(values)
            for v2 in values[i + 1 :]
        )
        if has_conflict:
            row_key = cell_key[:-1]
            col = cell_key[-1]
            key_dict = dict(zip(KEY_COLS, row_key))
            conflicts.append({"tipo": "MODIFICADA", "columna": col, **key_dict, "archivos": file_values})

    for row_key, file_values in new_map.items():
        if len(file_values) < 2:
            continue
        file_names = list(file_values.keys())
        has_conflict = False
        for col in val_cols:
            col_values = []
            for file_name in file_names:
                values_dict = file_values[file_name]
                col_values.append(values_dict.get(col, np.nan) if isinstance(values_dict, dict) else np.nan)
            if any(
                not np.isclose(v1, v2, rtol=RTOL, atol=0, equal_nan=True)
                for i, v1 in enumerate(col_values)
                for v2 in col_values[i + 1 :]
            ):
                has_conflict = True
                break
        if has_conflict:
            key_dict = dict(zip(KEY_COLS, row_key))
            conflicts.append(
                {
                    "tipo": "NUEVA",
                    "columna": "múltiples",
                    **key_dict,
                    "archivos": {name: file_values[name] for name in file_names},
                }
            )
    return conflicts


def _apply_diffs(df_acum: pd.DataFrame, df_new: pd.DataFrame, df_diffs: pd.DataFrame) -> pd.DataFrame:
    val_cols = [c for c in VALUE_COLS if c in df_acum.columns]
    key_cols = [c for c in KEY_COLS if c in df_acum.columns]

    nuevas = df_diffs[df_diffs["tipo_cambio"] == "NUEVA"][key_cols].drop_duplicates()
    if not nuevas.empty:
        filas_nuevas = pd.merge(nuevas, df_new[key_cols + val_cols], on=key_cols, how="left")
        acum_keys = set(df_acum.set_index(key_cols).index)
        nueva_idx = filas_nuevas.set_index(key_cols).index
        mask_exist = np.array(nueva_idx.isin(acum_keys))
        mask_solo = ~mask_exist

        if mask_solo.any():
            df_acum = pd.concat([df_acum, filas_nuevas[mask_solo]], ignore_index=True)

        if mask_exist.any():
            overwrite = filas_nuevas[mask_exist]
            df_acum = pd.merge(
                df_acum,
                overwrite[key_cols + val_cols],
                on=key_cols,
                how="left",
                suffixes=("", "_new"),
            )
            for col in val_cols:
                new_col = f"{col}_new"
                if new_col in df_acum.columns:
                    df_acum[col] = np.where(df_acum[new_col].notna(), df_acum[new_col], df_acum[col])
                    df_acum = df_acum.drop(columns=[new_col])

    mod = df_diffs[df_diffs["tipo_cambio"] == "MODIFICADA"].copy()
    if not mod.empty:
        mod["valor_nuevo"] = mod["valor_nuevo"].fillna(_SENTINEL)
        mod_pivot = (
            mod.pivot_table(
                index=key_cols,
                columns="columna",
                values="valor_nuevo",
                aggfunc="last",
            )
            .reset_index()
        )
        years_in_pivot = [c for c in mod_pivot.columns if c not in key_cols]
        df_acum = pd.merge(df_acum, mod_pivot, on=key_cols, how="left", suffixes=("", "_upd"))

        for col in years_in_pivot:
            upd_col = f"{col}_upd"
            if upd_col in df_acum.columns:
                df_acum[col] = np.where(
                    df_acum[upd_col].notna(),
                    df_acum[upd_col].astype(float),
                    df_acum[col].astype(float),
                )
                df_acum[col] = df_acum[col].replace(_SENTINEL, np.nan)
                df_acum = df_acum.drop(columns=[upd_col])

    return df_acum.reset_index(drop=True)


def _validate_apply(
    df_result: pd.DataFrame,
    df_diffs_applied: pd.DataFrame,
    filename: str,
) -> list[dict]:
    if df_diffs_applied.empty:
        return []

    key_cols = [c for c in KEY_COLS if c in df_result.columns]
    if not key_cols:
        return [
            {
                "archivo": filename,
                "tipo": "VALIDACION",
                "Parameter": "",
                "TECHNOLOGY": "",
                "FUEL": "",
                "columna": "—",
                "valor_esperado": "KEY_COLS presentes",
                "valor_actual": "no disponibles en resultado",
            }
        ]

    result_idx = df_result.set_index(key_cols)
    unapplied: list[dict] = []

    nuevas = df_diffs_applied[df_diffs_applied["tipo_cambio"] == "NUEVA"]
    for _, row in nuevas.iterrows():
        key = tuple(row[k] for k in key_cols)
        if key not in result_idx.index:
            unapplied.append(
                {
                    "archivo": filename,
                    "tipo": "NUEVA",
                    "Parameter": row.get("Parameter", ""),
                    "TECHNOLOGY": row.get("TECHNOLOGY", ""),
                    "FUEL": row.get("FUEL", ""),
                    "columna": "—",
                    "valor_esperado": "fila completa",
                    "valor_actual": "no existe",
                }
            )

    mods = df_diffs_applied[df_diffs_applied["tipo_cambio"] == "MODIFICADA"]
    for _, row in mods.iterrows():
        key = tuple(row[k] for k in key_cols)
        col = row["columna"]
        expected = row["valor_nuevo"]
        if key not in result_idx.index or col not in result_idx.columns:
            unapplied.append(
                {
                    "archivo": filename,
                    "tipo": "MODIFICADA",
                    "Parameter": row.get("Parameter", ""),
                    "TECHNOLOGY": row.get("TECHNOLOGY", ""),
                    "FUEL": row.get("FUEL", ""),
                    "columna": col,
                    "valor_esperado": expected,
                    "valor_actual": "fila/col no existe",
                }
            )
            continue
        actual = result_idx.loc[key, col]
        if isinstance(actual, pd.Series):
            actual = actual.iloc[0]
        if pd.isna(expected) and pd.isna(actual):
            continue
        if pd.isna(expected) != pd.isna(actual):
            unapplied.append(
                {
                    "archivo": filename,
                    "tipo": "MODIFICADA",
                    "Parameter": row.get("Parameter", ""),
                    "TECHNOLOGY": row.get("TECHNOLOGY", ""),
                    "FUEL": row.get("FUEL", ""),
                    "columna": col,
                    "valor_esperado": expected,
                    "valor_actual": actual,
                }
            )
            continue
        if not np.isclose(float(expected), float(actual), rtol=RTOL, atol=0):
            unapplied.append(
                {
                    "archivo": filename,
                    "tipo": "MODIFICADA",
                    "Parameter": row.get("Parameter", ""),
                    "TECHNOLOGY": row.get("TECHNOLOGY", ""),
                    "FUEL": row.get("FUEL", ""),
                    "columna": col,
                    "valor_esperado": expected,
                    "valor_actual": actual,
                }
            )
    return unapplied


# Máximo de entradas de faltantes en el resumen API (header JSON).
_EXPORT_VERIFY_MAX_FALTANTES = 20


def _verify_export_single_file(
    df_result: pd.DataFrame,
    df_new: pd.DataFrame,
    df_base: pd.DataFrame,
    filename: str,
    drop_techs: list[str],
    drop_fuels: list[str],
    faltantes_budget: list | None,
) -> dict:
    """
    Verifica que df_result (Excel integrado releído) refleje los cambios NUEVA/MODIFICADA
    de df_new vs df_base, excluyendo filas cubiertas por drop_techs/drop_fuels.
    """
    df_diffs = _detect_diffs(df_base, df_new)
    df_diffs = df_diffs[df_diffs["tipo_cambio"].isin(["NUEVA", "MODIFICADA"])].copy()

    n_omitidas = 0
    if drop_techs and "TECHNOLOGY" in df_diffs.columns:
        mask = df_diffs["TECHNOLOGY"].isin(drop_techs)
        n_omitidas += int(mask.sum())
        df_diffs = df_diffs[~mask]
    if drop_fuels and "FUEL" in df_diffs.columns:
        mask = df_diffs["FUEL"].isin(drop_fuels)
        n_omitidas += int(mask.sum())
        df_diffs = df_diffs[~mask]

    key_cols = [c for c in KEY_COLS if c in df_result.columns]
    faltantes: list[dict] = []
    n_ok_nuevas = 0
    n_ok_modif = 0

    if not key_cols:
        err = {
            "tipo": "VALIDACION",
            "Parameter": "",
            "TECHNOLOGY": "",
            "FUEL": "",
            "columna": "—",
            "valor_esperado": "KEY_COLS presentes",
            "valor_actual": "no disponibles en exportado",
        }
        if faltantes_budget is not None and len(faltantes_budget) < _EXPORT_VERIFY_MAX_FALTANTES:
            faltantes_budget.append(err)
        return {
            "archivo": filename,
            "n_verificadas_nuevas": 0,
            "n_verificadas_modif": 0,
            "n_omitidas_drop": n_omitidas,
            "n_faltantes": 1,
            "faltantes": [err],
            "ok": False,
        }

    result_idx = df_result.set_index(key_cols)

    nuevas = df_diffs[df_diffs["tipo_cambio"] == "NUEVA"]
    for _, row in nuevas.iterrows():
        key = tuple(row[k] for k in key_cols)
        if key in result_idx.index:
            n_ok_nuevas += 1
        else:
            item = {
                "tipo": "NUEVA",
                "Parameter": row.get("Parameter", ""),
                "TECHNOLOGY": row.get("TECHNOLOGY", ""),
                "FUEL": row.get("FUEL", ""),
                "columna": "—",
                "valor_esperado": "fila completa",
                "valor_actual": "no existe",
            }
            faltantes.append(item)
            if faltantes_budget is not None and len(faltantes_budget) < _EXPORT_VERIFY_MAX_FALTANTES:
                faltantes_budget.append(item)

    mods = df_diffs[df_diffs["tipo_cambio"] == "MODIFICADA"]
    for _, row in mods.iterrows():
        key = tuple(row[k] for k in key_cols)
        col = row["columna"]
        expected = row["valor_nuevo"]
        if key not in result_idx.index or col not in result_idx.columns:
            item = {
                "tipo": "MODIFICADA",
                "Parameter": row.get("Parameter", ""),
                "TECHNOLOGY": row.get("TECHNOLOGY", ""),
                "FUEL": row.get("FUEL", ""),
                "columna": col,
                "valor_esperado": expected,
                "valor_actual": "fila/col no existe",
            }
            faltantes.append(item)
            if faltantes_budget is not None and len(faltantes_budget) < _EXPORT_VERIFY_MAX_FALTANTES:
                faltantes_budget.append(item)
            continue
        actual = result_idx.loc[key, col]
        if isinstance(actual, pd.Series):
            actual = actual.iloc[0]
        if pd.isna(expected) and pd.isna(actual):
            n_ok_modif += 1
            continue
        if pd.isna(expected) != pd.isna(actual):
            item = {
                "tipo": "MODIFICADA",
                "Parameter": row.get("Parameter", ""),
                "TECHNOLOGY": row.get("TECHNOLOGY", ""),
                "FUEL": row.get("FUEL", ""),
                "columna": col,
                "valor_esperado": expected,
                "valor_actual": actual,
            }
            faltantes.append(item)
            if faltantes_budget is not None and len(faltantes_budget) < _EXPORT_VERIFY_MAX_FALTANTES:
                faltantes_budget.append(item)
            continue
        if np.isclose(float(expected), float(actual), rtol=RTOL, atol=0):
            n_ok_modif += 1
        else:
            item = {
                "tipo": "MODIFICADA",
                "Parameter": row.get("Parameter", ""),
                "TECHNOLOGY": row.get("TECHNOLOGY", ""),
                "FUEL": row.get("FUEL", ""),
                "columna": col,
                "valor_esperado": expected,
                "valor_actual": actual,
            }
            faltantes.append(item)
            if faltantes_budget is not None and len(faltantes_budget) < _EXPORT_VERIFY_MAX_FALTANTES:
                faltantes_budget.append(item)

    n_falt = len(faltantes)
    return {
        "archivo": filename,
        "n_verificadas_nuevas": n_ok_nuevas,
        "n_verificadas_modif": n_ok_modif,
        "n_omitidas_drop": n_omitidas,
        "n_faltantes": n_falt,
        "faltantes": faltantes[:_EXPORT_VERIFY_MAX_FALTANTES],
        "ok": n_falt == 0,
    }


def _build_export_verification(
    output_content: bytes,
    df_base: pd.DataFrame,
    names_new: list[str],
    dfs_new: list[pd.DataFrame],
    drop_techs: list[str],
    drop_fuels: list[str],
    conflictos_count: int,
) -> dict:
    """
    Doble verificación: relee el Excel exportado y contrasta NUEVA/MODIFICADA vs base por archivo nuevo.
    """
    budget: list[dict] = []
    try:
        df_export = _read_parameters_from_bytes(output_content)
    except Exception as exc:
        return {
            "ok": False,
            "applies_to_download": conflictos_count == 0,
            "verification_error": f"{type(exc).__name__}: {exc}",
            "total_nuevas_verificadas": 0,
            "total_modificadas_verificadas": 0,
            "total_omitidas_drop": 0,
            "total_faltantes": 0,
            "per_file": [],
            "faltantes_muestra": [],
        }

    per_file: list[dict] = []
    total_n = total_m = total_o = total_f = 0
    all_ok = True
    for name, df_n in zip(names_new, dfs_new):
        r = _verify_export_single_file(
            df_export, df_n, df_base, Path(name).name, drop_techs, drop_fuels, budget
        )
        per_file.append(
            {
                "archivo": r["archivo"],
                "ok": r["ok"],
                "n_verificadas_nuevas": r["n_verificadas_nuevas"],
                "n_verificadas_modif": r["n_verificadas_modif"],
                "n_omitidas_drop": r["n_omitidas_drop"],
                "n_faltantes": r["n_faltantes"],
            }
        )
        total_n += r["n_verificadas_nuevas"]
        total_m += r["n_verificadas_modif"]
        total_o += r["n_omitidas_drop"]
        total_f += r["n_faltantes"]
        if not r["ok"]:
            all_ok = False

    return {
        "ok": all_ok and total_f == 0,
        "applies_to_download": conflictos_count == 0,
        "verification_error": None,
        "total_nuevas_verificadas": total_n,
        "total_modificadas_verificadas": total_m,
        "total_omitidas_drop": total_o,
        "total_faltantes": total_f,
        "per_file": per_file,
        "faltantes_muestra": budget[:_EXPORT_VERIFY_MAX_FALTANTES],
    }


def _format_unapplied_warning(detail: dict) -> str:
    return (
        f"{detail.get('archivo', '')}: {detail.get('tipo', '')} "
        f"Parameter={detail.get('Parameter', '')} "
        f"TECHNOLOGY={detail.get('TECHNOLOGY', '')} "
        f"FUEL={detail.get('FUEL', '')} "
        f"col={detail.get('columna', '')} "
        f"esperado={detail.get('valor_esperado', '')} "
        f"actual={detail.get('valor_actual', '')}"
    )


def _extract_contribution(df_diffs: pd.DataFrame, archivo: str) -> dict:
    if df_diffs.empty:
        return {
            "archivo": archivo,
            "total_cambios": 0,
            "n_nuevas": 0,
            "n_eliminadas": 0,
            "n_modificadas": 0,
            "parametros": [],
            "tecnologias": [],
            "fuels": [],
        }

    datos = df_diffs[df_diffs["tipo_cambio"] != "ELIMINADA"].copy()

    def unique_non_empty(series: pd.Series) -> list[str]:
        return sorted(series.replace("", pd.NA).dropna().unique().tolist())

    return {
        "archivo": archivo,
        "total_cambios": len(df_diffs),
        "n_nuevas": int((df_diffs["tipo_cambio"] == "NUEVA").sum()),
        "n_eliminadas": int((df_diffs["tipo_cambio"] == "ELIMINADA").sum()),
        "n_modificadas": int((df_diffs["tipo_cambio"] == "MODIFICADA").sum()),
        "parametros": unique_non_empty(datos["Parameter"]) if "Parameter" in datos.columns else [],
        "tecnologias": unique_non_empty(datos["TECHNOLOGY"]) if "TECHNOLOGY" in datos.columns else [],
        "fuels": unique_non_empty(datos["FUEL"]) if "FUEL" in datos.columns else [],
    }


def _drop_keys(
    df: pd.DataFrame, drop_techs: list[str], drop_fuels: list[str]
) -> tuple[pd.DataFrame, int, int, pd.DataFrame]:
    mask_tech = pd.Series(False, index=df.index)
    mask_fuel = pd.Series(False, index=df.index)
    if drop_techs and "TECHNOLOGY" in df.columns:
        mask_tech = df["TECHNOLOGY"].isin(drop_techs)
    if drop_fuels and "FUEL" in df.columns:
        mask_fuel = df["FUEL"].isin(drop_fuels)
    n_tech = int(mask_tech.sum())
    n_fuel = int((mask_fuel & ~mask_tech).sum())
    mask_remove = mask_tech | mask_fuel
    df_out = df[~mask_remove].reset_index(drop=True)
    df_removed = df.loc[mask_remove].copy()
    if not df_removed.empty:
        mot = np.where(mask_tech[mask_remove].to_numpy(), "TECHNOLOGY", "FUEL")
        df_removed.insert(0, "motivo_eliminacion", mot)
    return df_out, n_tech, n_fuel, df_removed


class IntegrateSandService:
    """Orquesta la integracion SAND para uso via API."""

    @staticmethod
    def verify_integrated_export_standalone(
        base_filename: str,
        base_content: bytes,
        integrated_filename: str,
        integrated_content: bytes,
        new_files: list[tuple[str, bytes]],
        drop_techs_csv: str | None = None,
        drop_fuels_csv: str | None = None,
    ) -> dict:
        """
        Verifica un Excel integrado subido por el usuario (sin ejecutar la integración).
        Misma lógica que la doble verificación post-export en integrate_sand_files.
        """
        if not _is_allowed_excel(base_filename):
            raise ValueError(
                "El archivo base debe ser un Excel válido "
                f"({', '.join(sorted(ALLOWED_EXCEL_EXTENSIONS))})."
            )
        if not base_content:
            raise ValueError("El archivo base está vacío.")
        if not _is_allowed_excel(integrated_filename):
            raise ValueError(
                "El archivo integrado debe ser un Excel válido "
                f"({', '.join(sorted(ALLOWED_EXCEL_EXTENSIONS))})."
            )
        if not integrated_content:
            raise ValueError("El archivo integrado está vacío.")
        if not new_files:
            raise ValueError("Debes enviar al menos un archivo nuevo.")

        valid_new_files: list[tuple[str, bytes]] = []
        for filename, content in new_files:
            if not _is_allowed_excel(filename):
                continue
            if filename.startswith("~$"):
                continue
            if content:
                valid_new_files.append((filename, content))
        if not valid_new_files:
            raise ValueError(
                "No se encontraron archivos nuevos válidos "
                f"({', '.join(sorted(ALLOWED_EXCEL_EXTENSIONS))})."
            )

        df_base = _read_parameters_from_bytes(base_content)
        names_new: list[str] = []
        dfs_new: list[pd.DataFrame] = []
        for filename, content in valid_new_files:
            try:
                df_new = _read_parameters_from_bytes(content)
            except Exception as exc:
                raise ValueError(
                    f"{filename}: no se pudo leer hoja Parameters ({type(exc).__name__}: {exc})"
                ) from exc
            names_new.append(filename)
            dfs_new.append(df_new)

        drop_techs = _clean_csv_values(drop_techs_csv)
        drop_fuels = _clean_csv_values(drop_fuels_csv)

        export_verification = _build_export_verification(
            integrated_content,
            df_base,
            names_new,
            dfs_new,
            drop_techs,
            drop_fuels,
            0,
        )
        return {"export_verification": export_verification}

    @staticmethod
    def integrate_sand_files(
        base_filename: str,
        base_content: bytes,
        new_files: list[tuple[str, bytes]],
        drop_techs_csv: str | None = None,
        drop_fuels_csv: str | None = None,
        output_filename: str = "SAND_integrado.xlsx",
    ) -> dict:
        if not _is_allowed_excel(base_filename):
            raise ValueError(
                "El archivo base debe ser un Excel válido "
                f"({', '.join(sorted(ALLOWED_EXCEL_EXTENSIONS))})."
            )
        if not base_content:
            raise ValueError("El archivo base está vacío.")
        if not new_files:
            raise ValueError("Debes enviar al menos un archivo nuevo para integrar.")

        valid_new_files: list[tuple[str, bytes]] = []
        for filename, content in new_files:
            if not _is_allowed_excel(filename):
                continue
            if filename.startswith("~$"):
                continue
            if content:
                valid_new_files.append((filename, content))
        if not valid_new_files:
            raise ValueError(
                "No se encontraron archivos nuevos válidos "
                f"({', '.join(sorted(ALLOWED_EXCEL_EXTENSIONS))})."
            )

        warnings: list[str] = []
        errors: list[str] = []
        contributions: list[dict] = []
        conflicts: list[dict] = []
        df_acum: pd.DataFrame | None = None
        dropped_tech_rows = 0
        dropped_fuel_rows = 0
        log_text = ""
        read_errors: list[str] = []
        integration_rows: list[dict] = []
        contributions_for_log: list[dict] = []
        duplicate_messages: list[str] = []
        timing: dict[str, float] = {}
        t0 = time.time()
        diffs_vs_base: list[pd.DataFrame] = []
        names_new: list[str] = []
        duplicate_detail_frames: list[pd.DataFrame] = []
        cambios_excel_content = b""
        fatal_integration_error = False
        df_drop_removed = pd.DataFrame()
        drop_techs: list[str] = []
        drop_fuels: list[str] = []
        export_verification: dict | None = None

        try:
            df_base = _read_parameters_from_bytes(base_content)
            df_acum = df_base.copy()

            duplicate_detail_frames.append(_detect_duplicates_detail(df_base, Path(base_filename).name))

            dup_base = _detect_duplicates(df_base, Path(base_filename).name)
            duplicate_messages.extend(dup_base)
            warnings.extend(dup_base)

            readable_new_files: list[tuple[str, bytes]] = []
            dfs_new: list[pd.DataFrame] = []
            for filename, content in valid_new_files:
                try:
                    df_new = _read_parameters_from_bytes(content)
                except Exception as exc:
                    err_line = f"{filename}: no se pudo leer hoja Parameters ({type(exc).__name__}: {exc})"
                    errors.append(err_line)
                    read_errors.append(err_line)
                    continue
                readable_new_files.append((filename, content))
                dfs_new.append(df_new)
                duplicate_detail_frames.append(_detect_duplicates_detail(df_new, filename))
                dup_new = _detect_duplicates(df_new, filename)
                duplicate_messages.extend(dup_new)
                warnings.extend(dup_new)

            timing["read"] = time.time() - t0

            if not readable_new_files:
                raise ValueError("No se pudo leer ningún archivo nuevo válido para integrar.")

            names_new = [name for name, _ in readable_new_files]
            new_rows_counts = [len(df) for df in dfs_new]

            t_conf = time.time()
            diffs_vs_base = [_detect_diffs(df_base, df_n) for df_n in dfs_new]
            conflicts = _detect_conflicts(df_base, names_new, dfs_new, diffs_vs_base)
            timing["conflicts"] = time.time() - t_conf

            unapplied_all: list[dict] = []
            t_int = time.time()
            for (filename, _), df_new, diffs_base in zip(readable_new_files, dfs_new, diffs_vs_base):
                ti = time.time()
                contributions.append(_extract_contribution(diffs_base, filename))
                contributions_for_log.append(extract_contribution_with_combinaciones(diffs_base, filename))
                if not diffs_base.empty:
                    df_acum = _apply_diffs(df_acum, df_new, diffs_base)
                unapplied = _validate_apply(df_acum, diffs_base, filename)
                unapplied_all.extend(unapplied)
                counts_s = (
                    diffs_base["tipo_cambio"].value_counts()
                    if not diffs_base.empty
                    else pd.Series(dtype=int)
                )
                integration_rows.append(
                    {
                        "filename": filename,
                        "counts": {
                            "NUEVA": int(counts_s.get("NUEVA", 0)),
                            "ELIMINADA": int(counts_s.get("ELIMINADA", 0)),
                            "MODIFICADA": int(counts_s.get("MODIFICADA", 0)),
                        },
                        "seconds": time.time() - ti,
                        "unapplied": unapplied,
                    }
                )
            timing["integrate"] = time.time() - t_int

            if unapplied_all:
                warnings.append(f"TOTAL CAMBIOS NO APLICADOS: {len(unapplied_all)}")
                for detail in unapplied_all[:20]:
                    warnings.append(_format_unapplied_warning(detail))
                if len(unapplied_all) > 20:
                    warnings.append(f"... y {len(unapplied_all) - 20} cambios no aplicados adicionales")
            else:
                warnings.append("Todos los cambios se aplicaron correctamente.")

            drop_techs = _clean_csv_values(drop_techs_csv)
            drop_fuels = _clean_csv_values(drop_fuels_csv)
            n_rows_before_drop = len(df_acum)
            had_drop = bool(drop_techs or drop_fuels)
            if had_drop:
                df_acum, dropped_tech_rows, dropped_fuel_rows, df_drop_removed = _drop_keys(
                    df_acum, drop_techs, drop_fuels
                )

            summary_lines = [
                "INTEGRACION MULTIPLE SAND",
                f"Base: {Path(base_filename).name}",
                f"Archivos nuevos recibidos: {len(valid_new_files)}",
                f"Archivos nuevos procesados: {len(readable_new_files)}",
                f"Conflictos: {len(conflicts)}",
                f"Filas finales: {len(df_acum)}",
            ]
            if drop_techs or drop_fuels:
                summary_lines.append(
                    f"Filas removidas (tech/fuel): {dropped_tech_rows}/{dropped_fuel_rows}"
                )

        except Exception as exc:
            fatal_integration_error = True
            errors.append(f"ERROR FATAL: {type(exc).__name__}: {exc}")
            if isinstance(exc, KeyError):
                errors.append(
                    "Causa probable: algún archivo no tiene la columna esperada en KEY_COLS."
                )
            elif isinstance(exc, ValueError) and "broadcast" in str(exc).lower():
                errors.append(
                    "Causa probable: hay filas duplicadas en los keys de algún archivo."
                )
            elif isinstance(exc, FileNotFoundError):
                errors.append("Causa probable: verificar rutas de los archivos.")
            elif isinstance(exc, TypeError) and "dtype" in str(exc).lower():
                errors.append(
                    "Causa probable: columnas de año con tipo mixto (texto + número)."
                )
            errors.append(traceback.format_exc())
            warnings.append(
                "La integración falló con error fatal. No se generó el archivo Excel integrado; "
                "use el log adjunto para el detalle."
            )
            if df_acum is None:
                df_acum = pd.DataFrame()
            summary_lines = [
                "INTEGRACION MULTIPLE SAND",
                "ESTADO: ERROR FATAL",
                f"Base: {Path(base_filename).name}",
                "No se generó el Excel integrado (no se devuelve el archivo base como sustituto).",
                f"Conflictos detectados hasta el error: {len(conflicts)}",
            ]
            log_text = build_fatal_error_log(
                base_filename,
                [n for n, _ in valid_new_files],
                errors,
            )

        if fatal_integration_error:
            output_content = b""
            export_dt = 0.0
        else:
            output_buffer = BytesIO()
            t_exp_start = time.time()
            if "MODE_OF_OPERATION" in df_acum.columns:
                df_acum = df_acum.copy()
                df_acum["MODE_OF_OPERATION"] = normalize_mode_of_operation_series(
                    df_acum["MODE_OF_OPERATION"]
                )
            df_acum.to_excel(output_buffer, sheet_name="Parameters", index=False, engine="openpyxl")
            output_content = output_buffer.getvalue()
            export_dt = time.time() - t_exp_start
            export_verification = _build_export_verification(
                output_content,
                df_base,
                names_new,
                dfs_new,
                drop_techs,
                drop_fuels,
                len(conflicts),
            )

        if not log_text:
            validation_ok_msg = (
                None if unapplied_all else "Todos los cambios se aplicaron correctamente."
            )
            timing["export"] = export_dt
            timing["total"] = time.time() - t0
            log_text = build_integration_sand_log(
                base_filename=base_filename,
                paths_new=names_new,
                output_filename=output_filename,
                drop_techs=drop_techs,
                drop_fuels=drop_fuels,
                n_base_rows=len(df_base),
                new_rows_counts=new_rows_counts,
                duplicate_messages=duplicate_messages,
                conflicts=conflicts,
                integration_rows=integration_rows,
                contributions_for_log=contributions_for_log,
                unapplied_all=unapplied_all,
                warnings_validation_line=validation_ok_msg,
                drop_tech_rows=dropped_tech_rows,
                drop_fuel_rows=dropped_fuel_rows,
                n_rows_before_drop=n_rows_before_drop,
                n_rows_final=len(df_acum),
                had_drop=had_drop,
                timing={
                    "read": timing["read"],
                    "conflicts": timing["conflicts"],
                    "integrate": timing["integrate"],
                    "export": timing["export"],
                    "total": timing["total"],
                },
                errors=list(errors),
                read_errors=read_errors,
            )
            try:
                from app.services.integrate_sand_cambios_excel import build_cambios_workbook_bytes

                # Con conflictos entre archivos nuevos no se genera cambios_integracion (el ZIP lleva solo log + conflictos).
                if not conflicts:
                    cambios_excel_content = build_cambios_workbook_bytes(
                        base_filename=base_filename,
                        names_new=names_new,
                        diffs_vs_base=diffs_vs_base,
                        duplicate_detail_frames=duplicate_detail_frames,
                        unapplied_all=unapplied_all,
                        drop_techs=drop_techs,
                        drop_fuels=drop_fuels,
                        df_drop_removed=df_drop_removed,
                    )
            except Exception:
                cambios_excel_content = b""

        return {
            "output_filename": output_filename,
            "output_content": output_content,
            "total_filas": 0 if fatal_integration_error else len(df_acum),
            "contribuciones": contributions,
            "conflictos_count": len(conflicts),
            "conflictos": conflicts,
            "resumen": "\n".join(summary_lines),
            "warnings": warnings,
            "errors": errors,
            "log_text": log_text,
            "cambios_excel_content": cambios_excel_content,
            "integration_failed": fatal_integration_error,
            "export_verification": export_verification,
        }
