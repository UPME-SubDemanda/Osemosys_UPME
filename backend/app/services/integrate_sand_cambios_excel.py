"""Excel de detalle de cambios en integracion SAND (diffs vs base, conflictos, duplicados)."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

from app.services.integrate_sand_service import KEY_COLS


def _conflict_archivos_to_text(archivos: Any) -> str:
    if archivos is None:
        return ""
    try:
        return json.dumps(archivos, ensure_ascii=False, default=str)
    except TypeError:
        return str(archivos)


def build_cambios_workbook_bytes(
    *,
    base_filename: str,
    names_new: list[str],
    diffs_vs_base: list[pd.DataFrame],
    conflicts: list[dict[str, Any]],
    duplicate_detail_frames: list[pd.DataFrame],
    unapplied_all: list[dict[str, Any]],
) -> bytes:
    """Genera un .xlsx con hojas: Cambios_vs_base, Conflictos, Duplicados, Validacion."""
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # --- Portada / contexto (primera hoja) ---
        pd.DataFrame(
            {
                "campo": [
                    "archivo_base",
                    "n_archivos_nuevos",
                    "hoja_cambios",
                    "hoja_conflictos",
                    "hoja_duplicados",
                    "hoja_validacion",
                ],
                "valor": [
                    Path(base_filename).name,
                    len(names_new),
                    "Diferencias NUEVA / ELIMINADA / MODIFICADA vs la base (por archivo nuevo)",
                    "Celdas o filas en disputa entre archivos nuevos",
                    "Grupos con la misma clave repetida dentro de un mismo Excel",
                    "Cambios que no se pudieron verificar en el acumulado",
                ],
            }
        ).to_excel(writer, sheet_name="Leeme", index=False)

        # --- Cambios respecto al archivo base (misma logica que _detect_diffs en referencia) ---
        parts: list[pd.DataFrame] = []
        for name, df in zip(names_new, diffs_vs_base):
            if df.empty:
                continue
            d = df.copy()
            d.insert(0, "archivo_nuevo", Path(name).name)
            parts.append(d)
        if parts:
            df_cambios = pd.concat(parts, ignore_index=True)
            df_cambios.to_excel(writer, sheet_name="Cambios_vs_base", index=False)
        else:
            pd.DataFrame(
                {
                    "nota": [
                        "No hay filas de diferencia frente a la base en los archivos nuevos "
                        "(todos coinciden con el base para las claves comparadas)."
                    ]
                }
            ).to_excel(writer, sheet_name="Cambios_vs_base", index=False)

        # --- Conflictos entre archivos nuevos ---
        if conflicts:
            rows = []
            for c in conflicts:
                row: dict[str, Any] = {
                    "tipo": c.get("tipo"),
                    "columna": c.get("columna"),
                    "detalle_archivos_valores": _conflict_archivos_to_text(c.get("archivos")),
                }
                for k in KEY_COLS:
                    row[k] = c.get(k, "")
                rows.append(row)
            pd.DataFrame(rows).to_excel(writer, sheet_name="Conflictos", index=False)
        else:
            pd.DataFrame({"nota": ["Sin conflictos entre archivos nuevos."]}).to_excel(
                writer, sheet_name="Conflictos", index=False
            )

        # --- Duplicados internos por archivo (misma idea que paso [2/5] de la referencia) ---
        dup_parts = [df for df in duplicate_detail_frames if df is not None and not df.empty]
        if dup_parts:
            pd.concat(dup_parts, ignore_index=True).to_excel(writer, sheet_name="Duplicados", index=False)
        else:
            pd.DataFrame(
                {"nota": ["Sin filas duplicadas por clave (KEY_COLS) en base y archivos nuevos."]}
            ).to_excel(writer, sheet_name="Duplicados", index=False)

        # --- Validacion post-aplicacion ---
        if unapplied_all:
            pd.DataFrame(unapplied_all).to_excel(writer, sheet_name="Validacion", index=False)
        else:
            pd.DataFrame({"nota": ["Todos los cambios esperados quedaron reflejados en el resultado."]}).to_excel(
                writer, sheet_name="Validacion", index=False
            )

    buf.seek(0)
    return buf.getvalue()
