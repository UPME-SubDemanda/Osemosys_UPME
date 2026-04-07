"""Excel de detalle de cambios en integracion SAND (diffs vs base, duplicados).

Los conflictos entre archivos nuevos van en un archivo aparte: `build_conflictos_workbook_bytes`.
"""

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


def build_conflictos_workbook_bytes(conflicts: list[dict[str, Any]]) -> bytes:
    """Excel dedicado: solo disputas entre archivos nuevos (hoja Leeme + Conflictos)."""
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame(
            {
                "campo": ["Descripción", "Nota"],
                "valor": [
                    "Disputas entre archivos nuevos",
                    "Cada fila es una celda o fila nueva en la que dos o más archivos nuevos proponen "
                    "valores distintos para la misma clave. No incluye el Excel integrado ni otros informes.",
                ],
            }
        ).to_excel(writer, sheet_name="Leeme", index=False)

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
            pd.DataFrame(
                {"nota": ["No se registraron conflictos entre archivos nuevos (lista vacía)."]}
            ).to_excel(writer, sheet_name="Conflictos", index=False)

    buf.seek(0)
    return buf.getvalue()


def _write_eliminaciones_drop_sheet(
    writer: pd.ExcelWriter,
    *,
    drop_techs: list[str],
    drop_fuels: list[str],
    df_drop_removed: pd.DataFrame | None,
) -> None:
    sheet = "Eliminaciones_drop"
    if not drop_techs and not drop_fuels:
        pd.DataFrame(
            {
                "nota": [
                    "No se solicitó eliminación por tecnología ni por combustible "
                    "(listas vacías en la integración)."
                ]
            }
        ).to_excel(writer, sheet_name=sheet, index=False)
        return

    summary = pd.DataFrame(
        {
            "campo": [
                "tecnologías_solicitadas",
                "fuels_solicitados",
                "filas_eliminadas_total",
            ],
            "valor": [
                ", ".join(drop_techs) if drop_techs else "—",
                ", ".join(drop_fuels) if drop_fuels else "—",
                len(df_drop_removed) if df_drop_removed is not None else 0,
            ],
        }
    )
    summary.to_excel(writer, sheet_name=sheet, index=False, startrow=0)
    start_data = len(summary) + 2
    if df_drop_removed is not None and not df_drop_removed.empty:
        df_drop_removed.to_excel(writer, sheet_name=sheet, index=False, startrow=start_data)
    else:
        pd.DataFrame(
            {
                "nota": [
                    "0 filas coincidieron con las listas de tecnología o combustible "
                    "(ninguna fila del acumulado previo al drop coincidía)."
                ]
            }
        ).to_excel(writer, sheet_name=sheet, index=False, startrow=start_data)


def build_cambios_workbook_bytes(
    *,
    base_filename: str,
    names_new: list[str],
    diffs_vs_base: list[pd.DataFrame],
    duplicate_detail_frames: list[pd.DataFrame],
    unapplied_all: list[dict[str, Any]],
    drop_techs: list[str],
    drop_fuels: list[str],
    df_drop_removed: pd.DataFrame | None = None,
) -> bytes:
    """Genera un .xlsx con hojas: Cambios_vs_base, Duplicados, Validacion, Eliminaciones_drop."""
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # --- Portada / contexto (primera hoja) ---
        pd.DataFrame(
            {
                "campo": [
                    "archivo_base",
                    "n_archivos_nuevos",
                    "hoja_cambios",
                    "hoja_duplicados",
                    "hoja_validacion",
                    "hoja_eliminaciones_drop",
                    "conflictos_entre_nuevos",
                ],
                "valor": [
                    Path(base_filename).name,
                    len(names_new),
                    "Diferencias NUEVA / MODIFICADA vs la base (por archivo nuevo); "
                    "no se listan ausencias de clave respecto al base (antes ELIMINADA).",
                    "Grupos con la misma clave repetida dentro de un mismo Excel",
                    "Cambios que no se pudieron verificar en el acumulado",
                    "Filas quitadas por listas opcionales de tecnología/combustible al final de la integración",
                    "Si hubo disputas entre archivos nuevos, se entregan en el archivo conflictos_integracion.xlsx "
                    "(no en este libro).",
                ],
            }
        ).to_excel(writer, sheet_name="Leeme", index=False)

        # --- Cambios respecto al archivo base (sin filas tipo ELIMINADA en export) ---
        parts: list[pd.DataFrame] = []
        for name, df in zip(names_new, diffs_vs_base):
            if df.empty:
                continue
            d = df.copy()
            if "tipo_cambio" in d.columns:
                d = d[d["tipo_cambio"] != "ELIMINADA"]
            if d.empty:
                continue
            d.insert(0, "archivo_nuevo", Path(name).name)
            parts.append(d)
        if parts:
            df_cambios = pd.concat(parts, ignore_index=True)
            df_cambios.to_excel(writer, sheet_name="Cambios_vs_base", index=False)
        else:
            pd.DataFrame(
                {
                    "nota": [
                        "No hay filas NUEVA ni MODIFICADA frente a la base en los archivos nuevos "
                        "(o solo había diferencias por claves ausentes en el nuevo, no exportadas aquí)."
                    ]
                }
            ).to_excel(writer, sheet_name="Cambios_vs_base", index=False)

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

        _write_eliminaciones_drop_sheet(
            writer,
            drop_techs=drop_techs,
            drop_fuels=drop_fuels,
            df_drop_removed=df_drop_removed,
        )

    buf.seek(0)
    return buf.getvalue()
