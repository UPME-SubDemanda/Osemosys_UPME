"""Normalización canónica de MODE_OF_OPERATION para CSVs y catálogos."""

from __future__ import annotations

import pandas as pd


def normalize_mode_of_operation_scalar(v: object) -> str:
    """
    Normaliza un valor de MODE_OF_OPERATION a string canónico:
        1, 1.0, "1", "1.0" → "1"
        NaN, "", None      → ""
    Así se evitan conflictos al comparar/join entre archivos que guardan
    MOO como número y otros que lo guardan como texto.
    """
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(v, (int, float)):
        if isinstance(v, float) and not float(v).is_integer():
            return str(v).strip()
        return str(int(v))
    s = str(v).strip()
    if s == "" or s.lower() == "nan":
        return ""
    try:
        f = float(s)
        if f.is_integer():
            return str(int(f))
        return str(f)
    except ValueError:
        return s


def normalize_mode_of_operation_series(series: pd.Series) -> pd.Series:
    """Aplica normalize_mode_of_operation_scalar a cada elemento de la serie."""
    return series.map(normalize_mode_of_operation_scalar)
