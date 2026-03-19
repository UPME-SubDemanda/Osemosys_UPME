"""Servicio para integrar multiples archivos SAND en memoria.

Adapta la logica de referencia de `integrate_multi_sand.py` para uso en API:
- Entrada por bytes (UploadFile)
- Salida como bytes de Excel + resumen estructurado
"""

from __future__ import annotations

from collections import defaultdict
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd


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
_SENTINEL = -999999.123456789


def _is_allowed_excel(filename: str) -> bool:
    lower = filename.lower()
    return lower.endswith(".xlsm") or lower.endswith(".xlsx")


def _clean_csv_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _read_parameters_from_bytes(content: bytes) -> pd.DataFrame:
    df = pd.read_excel(BytesIO(content), sheet_name="Parameters", engine="calamine")

    for col in KEY_COLS:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

    for col in VALUE_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.dropna(how="all").reset_index(drop=True)


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


def _validate_apply(df_result: pd.DataFrame, df_diffs_applied: pd.DataFrame, filename: str) -> list[str]:
    if df_diffs_applied.empty:
        return []

    key_cols = [c for c in KEY_COLS if c in df_result.columns]
    result_idx = df_result.set_index(key_cols)
    warnings: list[str] = []

    nuevas = df_diffs_applied[df_diffs_applied["tipo_cambio"] == "NUEVA"]
    for _, row in nuevas.iterrows():
        key = tuple(row[k] for k in key_cols)
        if key not in result_idx.index:
            warnings.append(f"{filename}: fila NUEVA no aplicada para Parameter={row.get('Parameter', '')}")

    mods = df_diffs_applied[df_diffs_applied["tipo_cambio"] == "MODIFICADA"]
    for _, row in mods.iterrows():
        key = tuple(row[k] for k in key_cols)
        col = row["columna"]
        expected = row["valor_nuevo"]
        if key not in result_idx.index or col not in result_idx.columns:
            warnings.append(
                f"{filename}: celda MODIFICADA no aplicable ({row.get('Parameter', '')}, col={col})"
            )
            continue
        actual = result_idx.loc[key, col]
        if isinstance(actual, pd.Series):
            actual = actual.iloc[0]
        if pd.isna(expected) and pd.isna(actual):
            continue
        if pd.isna(expected) != pd.isna(actual):
            warnings.append(f"{filename}: celda MODIFICADA distinta ({row.get('Parameter', '')}, col={col})")
            continue
        if not np.isclose(float(expected), float(actual), rtol=RTOL, atol=0):
            warnings.append(f"{filename}: celda MODIFICADA distinta ({row.get('Parameter', '')}, col={col})")
    return warnings


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


def _drop_keys(df: pd.DataFrame, drop_techs: list[str], drop_fuels: list[str]) -> tuple[pd.DataFrame, int, int]:
    mask_tech = pd.Series(False, index=df.index)
    mask_fuel = pd.Series(False, index=df.index)
    if drop_techs and "TECHNOLOGY" in df.columns:
        mask_tech = df["TECHNOLOGY"].isin(drop_techs)
    if drop_fuels and "FUEL" in df.columns:
        mask_fuel = df["FUEL"].isin(drop_fuels)
    n_tech = int(mask_tech.sum())
    n_fuel = int((mask_fuel & ~mask_tech).sum())
    df_out = df[~(mask_tech | mask_fuel)].reset_index(drop=True)
    return df_out, n_tech, n_fuel


class IntegrateSandService:
    """Orquesta la integracion SAND para uso via API."""

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
            raise ValueError("El archivo base debe ser .xlsm o .xlsx.")
        if not base_content:
            raise ValueError("El archivo base está vacío.")
        if not new_files:
            raise ValueError("Debes enviar al menos un archivo nuevo para integrar.")

        valid_new_files: list[tuple[str, bytes]] = []
        for filename, content in new_files:
            if not _is_allowed_excel(filename):
                continue
            lower = filename.lower()
            if lower.startswith("sand_integrado") or filename.startswith("~$"):
                continue
            if content:
                valid_new_files.append((filename, content))
        if not valid_new_files:
            raise ValueError("No se encontraron archivos nuevos válidos (.xlsm/.xlsx).")

        df_base = _read_parameters_from_bytes(base_content)
        dfs_new = [_read_parameters_from_bytes(content) for _, content in valid_new_files]
        names_new = [name for name, _ in valid_new_files]

        diffs_vs_base = [_detect_diffs(df_base, df_n) for df_n in dfs_new]
        conflicts = _detect_conflicts(df_base, names_new, dfs_new, diffs_vs_base)

        df_acum = df_base.copy()
        contributions: list[dict] = []
        warnings: list[str] = []

        for (filename, _), df_new, diffs_base in zip(valid_new_files, dfs_new, diffs_vs_base):
            contributions.append(_extract_contribution(diffs_base, filename))
            if not diffs_base.empty:
                df_acum = _apply_diffs(df_acum, df_new, diffs_base)
            warnings.extend(_validate_apply(df_acum, diffs_base, filename))

        drop_techs = _clean_csv_values(drop_techs_csv)
        drop_fuels = _clean_csv_values(drop_fuels_csv)
        dropped_tech_rows = 0
        dropped_fuel_rows = 0
        if drop_techs or drop_fuels:
            df_acum, dropped_tech_rows, dropped_fuel_rows = _drop_keys(df_acum, drop_techs, drop_fuels)

        output_buffer = BytesIO()
        df_acum.to_excel(output_buffer, sheet_name="Parameters", index=False, engine="openpyxl")
        output_content = output_buffer.getvalue()

        summary_lines = [
            "INTEGRACION MULTIPLE SAND",
            f"Base: {Path(base_filename).name}",
            f"Archivos nuevos: {len(valid_new_files)}",
            f"Conflictos: {len(conflicts)}",
            f"Filas finales: {len(df_acum)}",
        ]
        if drop_techs or drop_fuels:
            summary_lines.append(
                f"Filas removidas (tech/fuel): {dropped_tech_rows}/{dropped_fuel_rows}"
            )

        return {
            "output_filename": output_filename,
            "output_content": output_content,
            "total_filas": len(df_acum),
            "contribuciones": contributions,
            "conflictos_count": len(conflicts),
            "resumen": "\n".join(summary_lines),
            "warnings": warnings,
        }
