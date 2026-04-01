"""Texto de informe estilo consola para integracion SAND (referencia: integrate_multi_sand.py)."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


def _fmt_list(items: list[str], max_items: int = 6) -> str:
    if not items:
        return "—"
    sample = ", ".join(str(v) for v in items[:max_items])
    extra = f" (+{len(items) - max_items} más)" if len(items) > max_items else ""
    return sample + extra


def append_conflicts_lines(conflictos: list[dict], lines: list[str]) -> None:
    sep = "!" * 68
    sep2 = "─" * 68

    if not conflictos:
        lines.append("")
        lines.append("  ✓ Sin conflictos entre archivos.")
        return

    mod_conflicts = [c for c in conflictos if c["tipo"] == "MODIFICADA"]
    new_conflicts = [c for c in conflictos if c["tipo"] == "NUEVA"]

    lines.append("")
    lines.append(sep)
    lines.append(
        f"  ⚠  CONFLICTOS DETECTADOS: {len(conflictos)}"
        f"  ({len(mod_conflicts)} en celdas  |  {len(new_conflicts)} en filas nuevas)"
    )
    lines.append("  La integración continúa — en cada conflicto gana el último archivo en orden.")
    lines.append(sep)

    if mod_conflicts:
        by_param: dict[str, list[dict]] = defaultdict(list)
        for c in mod_conflicts:
            by_param[str(c.get("Parameter", ""))].append(c)

        lines.append("")
        lines.append(f"  CELDAS MODIFICADAS EN CONFLICTO  ({len(mod_conflicts)})")
        lines.append(f"  {sep2}")
        for param, items in sorted(by_param.items()):
            lines.append("")
            lines.append(f"  ▸ {param}  ({len(items)} celda(s))")
            for c in items:
                tech = c.get("TECHNOLOGY") or "—"
                fuel = c.get("FUEL") or "—"
                col = c["columna"]
                lines.append(f"    · tech: {tech:<20s}  fuel: {fuel:<10s}  año: {col}")
                archivos = c.get("archivos") or {}
                for arch, val in archivos.items():
                    lines.append(f"        {str(arch):<35s} → {val}")

    if new_conflicts:
        lines.append("")
        lines.append(f"  FILAS NUEVAS EN CONFLICTO  ({len(new_conflicts)})")
        lines.append(f"  {sep2}")
        for c in new_conflicts:
            param = c.get("Parameter", "—")
            tech = c.get("TECHNOLOGY") or "—"
            fuel = c.get("FUEL") or "—"
            lines.append("")
            lines.append(f"  ▸ {param}  tech: {tech}  fuel: {fuel}")
            lines.append("    Archivos que la agregan con distintos valores:")
            archivos = c.get("archivos") or {}
            for arch in archivos:
                lines.append(f"        · {arch}")

    lines.append("")
    lines.append(f"{sep}")
    lines.append("")


def append_global_summary(contribuciones: list[dict[str, Any]], lines: list[str]) -> None:
    sep = "=" * 68
    sep2 = "─" * 68

    lines.append("")
    lines.append(sep)
    lines.append("  RESUMEN DE CONTRIBUCIONES POR ARCHIVO")
    lines.append(sep)

    archivos_con_cambios = [c for c in contribuciones if c.get("total_cambios", 0) > 0]
    archivos_sin_cambios = [c for c in contribuciones if c.get("total_cambios", 0) == 0]

    for i, contrib in enumerate(archivos_con_cambios, 1):
        nombre = Path(str(contrib["archivo"])).name
        lines.append("")
        lines.append(f"  [{i}] {nombre}")
        lines.append(
            f"      Nuevas: {contrib.get('n_nuevas', 0):,}  |  "
            f"Eliminadas: {contrib.get('n_eliminadas', 0):,}  |  "
            f"Modificadas: {contrib.get('n_modificadas', 0):,}"
        )
        lines.append(f"\n      Parámetros afectados ({len(contrib.get('parametros') or [])}):")
        lines.append(f"        {_fmt_list(list(contrib.get('parametros') or []))}")
        lines.append(f"\n      Tecnologías afectadas ({len(contrib.get('tecnologias') or [])}):")
        lines.append(f"        {_fmt_list(list(contrib.get('tecnologias') or []))}")
        lines.append(f"\n      Fuels afectados ({len(contrib.get('fuels') or [])}):")
        lines.append(f"        {_fmt_list(list(contrib.get('fuels') or []))}")
        lines.append("\n      Combinaciones Parameter × TECHNOLOGY × FUEL:")

        combo = contrib.get("combinaciones")
        if combo is None:
            combo_df = pd.DataFrame()
        elif isinstance(combo, pd.DataFrame):
            combo_df = combo
        else:
            combo_df = pd.DataFrame(combo)
        if combo_df.empty:
            lines.append("        —")
        else:
            for tipo, grp in combo_df.groupby("tipo_cambio", sort=True):
                lines.append(f"        [{tipo}]")
                for _, row in grp.iterrows():
                    param = row.get("Parameter", "—")
                    tech = row.get("TECHNOLOGY", "—") or "—"
                    fuel = row.get("FUEL", "—") or "—"
                    lines.append(f"          · {str(param):35s}  tech: {str(tech):20s}  fuel: {fuel}")

        lines.append("")
        lines.append(f"  {sep2}")

    if archivos_sin_cambios:
        lines.append("")
        lines.append("  Sin diferencias respecto al acumulado:")
        for c in archivos_sin_cambios:
            lines.append(f"    · {Path(str(c['archivo'])).name}")
        lines.append("")

    lines.append("")
    lines.append(sep)
    lines.append("  TABLA RESUMEN")
    lines.append(sep)
    lines.append(
        f"  {'Archivo':<35}  {'Nuevas':>7}  {'Elim.':>7}  {'Modif.':>9}  {'Paráms':>7}  {'Techs':>6}  {'Fuels':>6}"
    )
    lines.append(f"  {sep2}")
    for c in contribuciones:
        nombre = Path(str(c["archivo"])).name[:35]
        lines.append(
            f"  {nombre:<35}  "
            f"{c.get('n_nuevas', 0):>7,}  "
            f"{c.get('n_eliminadas', 0):>7,}  "
            f"{c.get('n_modificadas', 0):>9,}  "
            f"{len(c.get('parametros') or []):>7}  "
            f"{len(c.get('tecnologias') or []):>6}  "
            f"{len(c.get('fuels') or []):>6}"
        )
    lines.append(f"  {sep2}")
    lines.append("")


def extract_contribution_with_combinaciones(df_diffs: pd.DataFrame, archivo: str) -> dict[str, Any]:
    """Igual que referencia: incluye DataFrame combinaciones para el log."""
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
            "combinaciones": pd.DataFrame(),
        }

    datos = df_diffs[df_diffs["tipo_cambio"] != "ELIMINADA"].copy()

    def unique_non_empty(series: pd.Series) -> list[str]:
        return sorted(series.replace("", pd.NA).dropna().unique().tolist())

    combo_cols = [c for c in ["Parameter", "TECHNOLOGY", "FUEL", "tipo_cambio"] if c in datos.columns]
    combinaciones = (
        datos[combo_cols].drop_duplicates().sort_values(combo_cols).reset_index(drop=True)
        if combo_cols
        else pd.DataFrame()
    )

    return {
        "archivo": archivo,
        "total_cambios": len(df_diffs),
        "n_nuevas": int((df_diffs["tipo_cambio"] == "NUEVA").sum()),
        "n_eliminadas": int((df_diffs["tipo_cambio"] == "ELIMINADA").sum()),
        "n_modificadas": int((df_diffs["tipo_cambio"] == "MODIFICADA").sum()),
        "parametros": unique_non_empty(datos["Parameter"]) if "Parameter" in datos.columns else [],
        "tecnologias": unique_non_empty(datos["TECHNOLOGY"]) if "TECHNOLOGY" in datos.columns else [],
        "fuels": unique_non_empty(datos["FUEL"]) if "FUEL" in datos.columns else [],
        "combinaciones": combinaciones,
    }


def append_validation_unapplied(
    filename: str,
    unapplied: list[dict[str, Any]],
    lines: list[str],
) -> None:
    if not unapplied:
        return
    n_mod = sum(1 for u in unapplied if u.get("tipo") == "MODIFICADA")
    n_new = sum(1 for u in unapplied if u.get("tipo") == "NUEVA")
    lines.append(
        f"  ⚠ VALIDACIÓN FALLIDA para {filename}: "
        f"{n_mod} modificaciones y {n_new} filas nuevas NO aplicadas"
    )
    for detail in unapplied[:20]:
        lines.append(
            f"    · {str(detail.get('Parameter', '')):30s} tech={str(detail.get('TECHNOLOGY', '')):15s} "
            f"fuel={str(detail.get('FUEL', '')):10s} col={detail.get('columna')} "
            f"esperado={detail.get('valor_esperado')} actual={detail.get('valor_actual')}"
        )
    if len(unapplied) > 20:
        lines.append(f"    ... y {len(unapplied) - 20} más")


def build_integration_sand_log(
    *,
    base_filename: str,
    paths_new: list[str],
    output_filename: str,
    drop_techs: list[str],
    drop_fuels: list[str],
    n_base_rows: int,
    new_rows_counts: list[int],
    duplicate_messages: list[str],
    conflicts: list[dict],
    integration_rows: list[dict[str, Any]],
    contributions_for_log: list[dict[str, Any]],
    unapplied_all: list[dict[str, Any]],
    warnings_validation_line: str | None,
    drop_tech_rows: int,
    drop_fuel_rows: int,
    n_rows_before_drop: int,
    n_rows_final: int,
    had_drop: bool,
    timing: dict[str, float],
    errors: list[str],
    read_errors: list[str],
) -> str:
    """
    integration_rows: por archivo en orden, con keys:
      filename, counts dict (NUEVA, ELIMINADA, MODIFICADA), seconds, unapplied (list)
    """
    lines: list[str] = []
    sep = "=" * 68

    def p(msg: str = "") -> None:
        lines.append(msg)

    p("")
    p(sep)
    p("  INTEGRACIÓN MÚLTIPLE SAND (API)")
    p(f"  Base   : {Path(base_filename).name}")
    p(f"  Nuevos : {len(paths_new)} archivo(s)")
    for pn in paths_new:
        p(f"           · {Path(pn).name}")
    p(f"  Salida : {output_filename}")
    if drop_techs:
        p(f"  Eliminar techs : {', '.join(drop_techs)}")
    if drop_fuels:
        p(f"  Eliminar fuels : {', '.join(drop_fuels)}")
    p(sep)

    p("")
    p("[1/5] Leyendo archivos...")
    p(f"      Base: {n_base_rows:,} filas")
    for pn, nrows in zip(paths_new, new_rows_counts):
        p(f"      Leyendo {Path(pn).name} ... ({nrows:,} filas)")
    if read_errors:
        for e in read_errors:
            p(f"      (omitido / error) {e}")

    p("")
    p("[2/5] Verificando duplicados...")
    if duplicate_messages:
        for msg in duplicate_messages:
            p(f"  ⚠ {msg}")
    else:
        p("  ✓ Sin duplicados en ningún archivo (o no detectados).")

    p("")
    p("[3/5] Detectando conflictos entre archivos...")
    append_conflicts_lines(conflicts, lines)

    p("[4/5] Integrando en orden...")
    for i, row in enumerate(integration_rows, 1):
        nombre = Path(row["filename"]).name
        counts = row.get("counts") or {}
        nu = counts.get("NUEVA", 0)
        el = counts.get("ELIMINADA", 0)
        mo = counts.get("MODIFICADA", 0)
        p(
            f"      [{i}/{len(integration_rows)}] {nombre}  →  "
            f"Nuevas: {nu:,}  "
            f"Elim.: {el:,}  "
            f"Modif.: {mo:,}  "
            f"({row.get('seconds', 0):.1f}s)"
        )
        unapplied_file = row.get("unapplied") or []
        if unapplied_file:
            append_validation_unapplied(nombre, unapplied_file, lines)

    append_global_summary(contributions_for_log, lines)

    if unapplied_all:
        p(f"\n  ⚠ TOTAL CAMBIOS NO APLICADOS: {len(unapplied_all)}")
    elif warnings_validation_line:
        p(f"\n  ✓ {warnings_validation_line}")

    if had_drop:
        p("")
        p(sep)
        p("  ELIMINACIÓN DE TECNOLOGÍAS / FUELS")
        p(sep)
        n_total = n_rows_before_drop - n_rows_final
        if drop_techs:
            p(f"  Tecnologías eliminadas : {', '.join(drop_techs)}")
            p(f"  Filas removidas por tech  : {drop_tech_rows:,}")
        if drop_fuels:
            p(f"  Fuels eliminados       : {', '.join(drop_fuels)}")
            p(f"  Filas removidas por fuel  : {drop_fuel_rows:,}")
        p(f"  Total filas removidas     : {n_total:,}")
        p(f"  Filas restantes           : {n_rows_final:,}")
        p(sep)

    p("")
    p(f"[5/5] Exportación en memoria: {n_rows_final:,} filas  ({timing.get('export', 0):.1f}s)")

    p(
        f"""
  Lectura      : {timing.get('read', 0):5.1f}s
  Conflictos   : {timing.get('conflicts', 0):5.1f}s
  Integración  : {timing.get('integrate', 0):5.1f}s
  Exportación  : {timing.get('export', 0):5.1f}s
  TOTAL        : {timing.get('total', 0):5.1f}s
"""
    )

    if errors:
        p("!" * 68)
        p("  ERRORES / ADVERTENCIAS FINALES")
        p("!" * 68)
        for e in errors:
            for line in str(e).split("\n"):
                p(f"  {line}")

    return "\n".join(lines)


def build_fatal_error_log(base_filename: str, new_names: list[str], errors: list[str]) -> str:
    """Informe mínimo cuando falla la integración antes o durante el proceso."""
    lines: list[str] = [
        "",
        "=" * 68,
        "  INTEGRACIÓN MÚLTIPLE SAND (API) — ERROR",
        f"  Base: {Path(base_filename).name}",
        "=" * 68,
        "",
    ]
    if new_names:
        lines.append(f"  Archivos nuevos: {len(new_names)}")
        for n in new_names:
            lines.append(f"    · {Path(n).name}")
        lines.append("")
    lines.append("!" * 68)
    for e in errors:
        for line in str(e).split("\n"):
            lines.append(f"  {line}")
    lines.append("!" * 68)
    return "\n".join(lines)
