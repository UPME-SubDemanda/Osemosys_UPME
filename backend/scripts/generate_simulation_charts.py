"""Genera graficas PNG y reporte HTML desde simulation_result.json."""

from __future__ import annotations

import argparse
import colorsys
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

FAMILIAS_TEC: dict[str, list[str]] = {
    "SOLAR": ["PWRSOLRTP", "PWRSOLRTP_ZNI", "PWRSOLUGE", "PWRSOLUGE_BAT", "PWRSOLUPE"],
    "HIDRO": ["PWRHYDDAM", "PWRHYDROR", "PWRHYDROR_NDC"],
    "EOLICA": ["PWRWNDONS", "PWRWNDOFS_FIX", "PWRWNDOFS_FLO"],
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
    "NUCLEAR": ["PWRNUC"],
    "BIOMASA_RESIDUOS": ["PWRAFR", "PWRBGS", "PWRWAS"],
    "OTRAS": ["PWRCSP", "PWRGEO", "PWRSTD"],
}

COLOR_BASE_FAMILIA: dict[str, str] = {
    "SOLAR": "#FDB813",
    "HIDRO": "#1F77B4",
    "EOLICA": "#2CA02C",
    "TERMICA_FOSIL": "#2B2B2B",
    "NUCLEAR": "#7B3F98",
    "BIOMASA_RESIDUOS": "#8C6D31",
    "OTRAS": "#17BECF",
}

COLORES_GRUPOS: dict[str, str] = {
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

FALLBACK_COLORS = ["#94a3b8", "#64748b", "#475569", "#334155", "#1e293b", "#0f172a"]


def _is_year(v: object) -> bool:
    try:
        y = int(v)
    except Exception:
        return False
    return 1900 <= y <= 3000


def _extract_year(index: list[object]) -> int | None:
    for token in reversed(index):
        if _is_year(token):
            return int(token)
    return None


def _hex_to_rgb01(hex_color: str) -> tuple[float, float, float]:
    c = hex_color.lstrip("#")
    return (int(c[0:2], 16) / 255.0, int(c[2:4], 16) / 255.0, int(c[4:6], 16) / 255.0)


def _rgb01_to_hex(r: float, g: float, b: float) -> str:
    return "#" + "".join(f"{max(0, min(255, int(round(v * 255)))):02x}" for v in (r, g, b))


def _generar_tonos(color_hex: str, n: int) -> list[str]:
    r, g, b = _hex_to_rgb01(color_hex)
    h, _l, s = colorsys.rgb_to_hls(r, g, b)
    tonos: list[str] = []
    for i in range(max(1, n)):
        li = 0.35 + (0.35 * i) / max(1, n - 1)
        si = s if s < 0.2 else min(1.0, s * 1.05)
        rr, gg, bb = colorsys.hls_to_rgb(h, li, si)
        tonos.append(_rgb01_to_hex(rr, gg, bb))
    return tonos


def _build_color_map_pwr() -> dict[str, str]:
    cmap: dict[str, str] = {}
    for familia, tecnologias in FAMILIAS_TEC.items():
        base = COLOR_BASE_FAMILIA.get(familia, "#888888")
        tonos = _generar_tonos(base, len(tecnologias))
        for i, tech in enumerate(tecnologias):
            cmap[tech] = tonos[i] if i < len(tonos) else base
    return cmap


COLOR_MAP_PWR = _build_color_map_pwr()


def _asignar_grupo(nombre: str) -> str:
    n = (nombre or "").upper()
    if "ELC" in n:
        return "ELC"
    if "JET" in n:
        return "JET"
    if "LPG" in n:
        return "LPG"
    if "BDL" in n:
        return "BDL"
    if "WAS" in n:
        return "WAS"
    if "BGS" in n:
        return "BGS"
    if "GSL" in n:
        return "GSL"
    if "DSL" in n:
        return "DSL"
    if "NGS" in n:
        return "NGS"
    if "BAG" in n:
        return "BAG"
    if "COA" in n:
        return "COA"
    if "WOO" in n:
        return "WOO"
    if "FOL" in n:
        return "FOL"
    if "AUT" in n:
        return "AUT"
    if "APHEV" in n:
        return "PHEV"
    if "AHEV" in n:
        return "HEV"
    return nombre.strip() if nombre else "OTRO"


def _get_color_for_technology(tech_name: str, fallback_idx: int) -> tuple[str, int]:
    key = (tech_name or "N/D").strip()
    if key in COLOR_MAP_PWR:
        return COLOR_MAP_PWR[key], fallback_idx
    key_upper = key.upper()
    for familia, techs in FAMILIAS_TEC.items():
        for idx, tech in enumerate(techs):
            if key == tech or key_upper.startswith(tech) or tech.startswith(key_upper):
                base = COLOR_BASE_FAMILIA.get(familia, "#17BECF")
                tonos = _generar_tonos(base, len(techs))
                return (tonos[idx] if idx < len(tonos) else base), fallback_idx
    color = FALLBACK_COLORS[fallback_idx % len(FALLBACK_COLORS)]
    return color, fallback_idx + 1


def _sort_time_labels(labels: list[str]) -> list[str]:
    if all(lbl.isdigit() for lbl in labels):
        return sorted(labels, key=lambda x: int(x))
    return sorted(labels)


def _build_series(
    rows: list[dict],
    *,
    time_getter,
    category_getter,
    value_getter,
    min_value: float = 1e-5,
    top_n: int = 16,
    accumulate: bool = False,
) -> tuple[list[str], list[str], dict[str, list[float]]]:
    raw: dict[tuple[str, str], float] = defaultdict(float)
    totals_by_category: dict[str, float] = defaultdict(float)
    time_set: set[str] = set()

    for row in rows:
        time_key = time_getter(row)
        category = category_getter(row)
        if time_key is None or category is None:
            continue
        value = float(value_getter(row) or 0.0)
        if abs(value) <= min_value:
            continue
        t = str(time_key)
        c = str(category)
        raw[(t, c)] += value
        totals_by_category[c] += value
        time_set.add(t)

    times = _sort_time_labels(list(time_set))
    if not times:
        return [], [], {}

    categories_sorted = sorted(totals_by_category.keys(), key=lambda c: totals_by_category[c], reverse=True)
    keep = set(categories_sorted[:top_n])
    if len(categories_sorted) > top_n:
        keep.add("OTROS")

    collapsed: dict[tuple[str, str], float] = defaultdict(float)
    for (time_key, category), value in raw.items():
        key_cat = category if category in keep else "OTROS"
        collapsed[(time_key, key_cat)] += value

    categories = [c for c in categories_sorted if c in keep and c != "OTROS"]
    if "OTROS" in keep:
        categories.append("OTROS")

    values_by_category: dict[str, list[float]] = {}
    for category in categories:
        values = [collapsed.get((t, category), 0.0) for t in times]
        if accumulate:
            acc = 0.0
            acc_values: list[float] = []
            for val in values:
                acc += val
                acc_values.append(acc)
            values = acc_values
        values_by_category[category] = values
    return times, categories, values_by_category


def _save_stacked_bar_chart(
    times: list[str],
    categories: list[str],
    values_by_category: dict[str, list[float]],
    colors_by_category: dict[str, str] | None = None,
    *,
    title: str,
    x_label: str,
    y_label: str,
    output_path: Path,
) -> None:
    plt.figure(figsize=(12, 5.2))
    if times and categories:
        x = times
        bottom = [0.0] * len(times)
        colors = plt.cm.tab20.colors
        for idx, cat in enumerate(categories):
            vals = values_by_category.get(cat, [0.0] * len(times))
            plt.bar(
                x,
                vals,
                bottom=bottom,
                label=cat,
                color=(colors_by_category.get(cat) if colors_by_category else None) or colors[idx % len(colors)],
                linewidth=0,
            )
            bottom = [bottom[i] + vals[i] for i in range(len(times))]
        ncols = 5 if len(categories) <= 15 else 6
        plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=ncols, fontsize=8, frameon=False)
    else:
        plt.text(0.5, 0.5, "Sin datos", ha="center", va="center", transform=plt.gca().transAxes)
    plt.title(title)
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=140)
    plt.close()


def _save_bar_chart(
    x_labels: list[str],
    y_values: list[float],
    *,
    title: str,
    x_label: str,
    y_label: str,
    output_path: Path,
) -> None:
    plt.figure(figsize=(10, 4.8))
    if x_labels:
        plt.bar(x_labels, y_values)
    else:
        plt.text(0.5, 0.5, "Sin datos", ha="center", va="center", transform=plt.gca().transAxes)
    plt.title(title)
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=140)
    plt.close()


def _sum_by_year(rows: list[dict], value_key: str) -> tuple[list[str], list[float]]:
    totals: dict[int, float] = defaultdict(float)
    for row in rows or []:
        year = row.get("year")
        if year is None:
            continue
        totals[int(year)] += float(row.get(value_key) or 0.0)
    years = sorted(totals.keys())
    return [str(y) for y in years], [totals[y] for y in years]


def _is_ref_import_tech(tech: str) -> bool:
    u = (tech or "").upper()
    return u.startswith("UPSREF") or u.startswith("IMPDSL") or u.startswith("IMPGSL") or u.startswith("IMPLPG")


def _colors_for_power_techs(categories: list[str]) -> dict[str, str]:
    colors: dict[str, str] = {}
    fb_idx = 0
    for tech in categories:
        c, fb_idx = _get_color_for_technology(tech, fb_idx)
        colors[tech] = c
    return colors


def _colors_for_fuel_groups(categories: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for cat in categories:
        out[cat] = COLORES_GRUPOS.get(cat, "#333333")
    return out


def _plot_series(
    image_name: str,
    section_images: dict[str, list[str]],
    section: str,
    times: list[str],
    categories: list[str],
    values_by_category: dict[str, list[float]],
    colors_by_category: dict[str, str],
    *,
    output_dir: Path,
    title: str,
    x_label: str,
    y_label: str,
) -> None:
    _save_stacked_bar_chart(
        times,
        categories,
        values_by_category,
        colors_by_category,
        title=title,
        x_label=x_label,
        y_label=y_label,
        output_path=output_dir / image_name,
    )
    section_images.setdefault(section, []).append(image_name)


def _write_html_report(
    result: dict,
    *,
    output_path: Path,
    section_images: dict[str, list[str]],
) -> None:
    section_html_parts: list[str] = []
    for section, images in section_images.items():
        if not images:
            continue
        cards = "\n".join(
            f'<div class="chart"><h3>{img.replace("_", " ").replace(".png", "").title()}</h3><img src="{img}" /></div>'
            for img in images
        )
        section_html_parts.append(f"<h2>{section}</h2>\n{cards}")

    sections_html = "\n".join(section_html_parts)
    html = f"""<!doctype html>
<html lang=\"es\">
<head>
  <meta charset=\"utf-8\" />
  <title>Reporte de simulaci�n local</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; }}
    h1 {{ margin-bottom: 8px; }}
    .muted {{ color: #555; margin-bottom: 20px; }}
    table {{ border-collapse: collapse; margin-bottom: 28px; min-width: 480px; }}
    td, th {{ border: 1px solid #ccc; padding: 8px 10px; text-align: left; }}
    th {{ background: #f5f5f5; }}
    .chart {{ margin-bottom: 24px; }}
    .chart img {{ max-width: 100%; border: 1px solid #ddd; }}
  </style>
</head>
<body>
  <h1>Reporte de simulaci�n local</h1>
  <p class=\"muted\">Generado desde simulation_result.json</p>
  {sections_html}
</body>
</html>
"""
    output_path.write_text(html, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generar charts PNG + HTML de simulaci�n")
    parser.add_argument("--result-json", type=Path, required=True, help="Ruta a simulation_result.json")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Carpeta de salida para PNG/HTML (default: <carpeta_json>/charts)",
    )
    args = parser.parse_args()

    result_json = args.result_json
    if not result_json.is_file():
        print(f"[ERROR] No existe archivo: {result_json}")
        return 1

    result = json.loads(result_json.read_text(encoding="utf-8"))
    output_dir = args.output_dir or (result_json.parent / "charts")
    output_dir.mkdir(parents=True, exist_ok=True)

    section_images: dict[str, list[str]] = {
        "Matriz electrica": [],
        "Gas y refinerias": [],
        "Sectores": [],
    }

    intermediate = result.get("intermediate_variables") or {}

    # Matriz electrica
    dispatch_rows = [r for r in (result.get("dispatch") or []) if str(r.get("technology_name") or "").upper().startswith("PWR")]
    d_times, d_cats, d_vals = _build_series(
        dispatch_rows,
        time_getter=lambda r: int(r.get("year")) if r.get("year") is not None else None,
        category_getter=lambda r: str(r.get("technology_name") or "N/D"),
        value_getter=lambda r: r.get("dispatch"),
        top_n=18,
    )
    _plot_series(
        "dispatch_by_year.png",
        section_images,
        "Matriz electrica",
        d_times,
        d_cats,
        d_vals,
        _colors_for_power_techs(d_cats),
        output_dir=output_dir,
        title="Generacion de electricidad por tecnologia (PWR)",
        x_label="A�o",
        y_label="PJ",
    )

    newcap_rows = [r for r in (result.get("new_capacity") or []) if str(r.get("technology_name") or "").upper().startswith("PWR")]
    nc_times, nc_cats, nc_vals = _build_series(
        newcap_rows,
        time_getter=lambda r: int(r.get("year")) if r.get("year") is not None else None,
        category_getter=lambda r: str(r.get("technology_name") or "N/D"),
        value_getter=lambda r: r.get("new_capacity"),
        top_n=18,
    )
    _plot_series(
        "new_capacity_by_year.png",
        section_images,
        "Matriz electrica",
        nc_times,
        nc_cats,
        nc_vals,
        _colors_for_power_techs(nc_cats),
        output_dir=output_dir,
        title="Capacidad nueva por tecnologia (PWR)",
        x_label="A�o",
        y_label="Capacidad",
    )

    anc_times, anc_cats, anc_vals = _build_series(
        newcap_rows,
        time_getter=lambda r: int(r.get("year")) if r.get("year") is not None else None,
        category_getter=lambda r: str(r.get("technology_name") or "N/D"),
        value_getter=lambda r: r.get("new_capacity"),
        top_n=18,
        accumulate=True,
    )
    _plot_series(
        "accumulated_new_capacity_by_year.png",
        section_images,
        "Matriz electrica",
        anc_times,
        anc_cats,
        anc_vals,
        _colors_for_power_techs(anc_cats),
        output_dir=output_dir,
        title="Capacidad nueva acumulada por tecnologia (PWR)",
        x_label="A�o",
        y_label="Capacidad acumulada",
    )

    total_cap = intermediate.get("TotalCapacityAnnual") or []
    tc_rows: list[dict] = []
    for it in total_cap:
        idx = it.get("index") or []
        if len(idx) < 3:
            continue
        tech = str(idx[1] or "")
        year = _extract_year(idx)
        if not tech.upper().startswith("PWR") or year is None:
            continue
        tc_rows.append({"year": year, "tech": tech, "value": float(it.get("value") or 0.0)})
    tc_times, tc_cats, tc_vals = _build_series(
        tc_rows,
        time_getter=lambda r: r["year"],
        category_getter=lambda r: r["tech"],
        value_getter=lambda r: r["value"],
        top_n=18,
    )
    _plot_series(
        "total_capacity_annual_by_year.png",
        section_images,
        "Matriz electrica",
        tc_times,
        tc_cats,
        tc_vals,
        _colors_for_power_techs(tc_cats),
        output_dir=output_dir,
        title="Capacidad total anual por tecnologia (PWR)",
        x_label="A�o",
        y_label="Capacidad",
    )

    # Gas y refinerias
    prod = intermediate.get("ProductionByTechnology") or []
    use = intermediate.get("UseByTechnology") or []

    def _rows_from_intermediate(items: list[dict]) -> list[dict]:
        rows: list[dict] = []
        for it in items:
            idx = it.get("index") or []
            if len(idx) < 4:
                continue
            year = _extract_year(idx)
            if year is None:
                continue
            rows.append(
                {
                    "year": year,
                    "tech": str(idx[1] or ""),
                    "fuel": str(idx[2] or ""),
                    "value": float(it.get("value") or 0.0),
                }
            )
        return rows

    prod_rows = _rows_from_intermediate(prod)
    use_rows = _rows_from_intermediate(use)

    oferta_rows = [r for r in prod_rows if r["tech"].upper().startswith("UPSREG") or r["tech"].upper().startswith("MINNGS")]
    o_times, o_cats, o_vals = _build_series(
        oferta_rows,
        time_getter=lambda r: r["year"],
        category_getter=lambda r: r["tech"],
        value_getter=lambda r: r["value"],
        top_n=14,
    )
    _plot_series(
        "gas_supply_by_year.png",
        section_images,
        "Gas y refinerias",
        o_times,
        o_cats,
        o_vals,
        _colors_for_fuel_groups([_asignar_grupo(c) for c in o_cats]),
        output_dir=output_dir,
        title="Oferta de gas natural",
        x_label="A�o",
        y_label="PJ",
    )

    cons_rows = [r for r in use_rows if "NGS" in r["tech"].upper()]
    c_times, c_cats, c_vals = _build_series(
        cons_rows,
        time_getter=lambda r: r["year"],
        category_getter=lambda r: r["tech"],
        value_getter=lambda r: r["value"],
        top_n=14,
    )
    _plot_series(
        "gas_consumption_by_year.png",
        section_images,
        "Gas y refinerias",
        c_times,
        c_cats,
        c_vals,
        _colors_for_fuel_groups([_asignar_grupo(c) for c in c_cats]),
        output_dir=output_dir,
        title="Consumo de gas natural",
        x_label="A�o",
        y_label="PJ",
    )

    ref_prod_rows = [r for r in prod_rows if r["tech"].upper().startswith("UPSREF")]
    rp_times, rp_cats, rp_vals = _build_series(
        ref_prod_rows,
        time_getter=lambda r: r["year"],
        category_getter=lambda r: _asignar_grupo(f"{r['tech']}_{r['fuel']}"),
        value_getter=lambda r: r["value"],
        top_n=12,
    )
    _plot_series(
        "refinery_production_by_year.png",
        section_images,
        "Gas y refinerias",
        rp_times,
        rp_cats,
        rp_vals,
        _colors_for_fuel_groups(rp_cats),
        output_dir=output_dir,
        title="Refinerias - Produccion por grupo de combustible",
        x_label="A�o",
        y_label="PJ",
    )

    ref_use_rows = [r for r in use_rows if r["tech"].upper().startswith("UPSREF")]
    ru_times, ru_cats, ru_vals = _build_series(
        ref_use_rows,
        time_getter=lambda r: r["year"],
        category_getter=lambda r: _asignar_grupo(f"{r['tech']}_{r['fuel']}"),
        value_getter=lambda r: r["value"],
        top_n=12,
    )
    _plot_series(
        "refinery_use_by_year.png",
        section_images,
        "Gas y refinerias",
        ru_times,
        ru_cats,
        ru_vals,
        _colors_for_fuel_groups(ru_cats),
        output_dir=output_dir,
        title="Refinerias - Consumo por grupo de combustible",
        x_label="A�o",
        y_label="PJ",
    )

    refimp_prod_rows = [r for r in prod_rows if _is_ref_import_tech(r["tech"])]
    rip_times, rip_cats, rip_vals = _build_series(
        refimp_prod_rows,
        time_getter=lambda r: r["year"],
        category_getter=lambda r: r["tech"],
        value_getter=lambda r: r["value"],
        top_n=12,
    )
    _plot_series(
        "refinery_import_production_by_year.png",
        section_images,
        "Gas y refinerias",
        rip_times,
        rip_cats,
        rip_vals,
        _colors_for_fuel_groups([_asignar_grupo(t) for t in rip_cats]),
        output_dir=output_dir,
        title="Refinerias + importaciones - Produccion",
        x_label="A�o",
        y_label="PJ",
    )

    refimp_use_rows = [r for r in use_rows if _is_ref_import_tech(r["tech"])]
    riu_times, riu_cats, riu_vals = _build_series(
        refimp_use_rows,
        time_getter=lambda r: r["year"],
        category_getter=lambda r: r["tech"],
        value_getter=lambda r: r["value"],
        top_n=12,
    )
    _plot_series(
        "refinery_import_use_by_year.png",
        section_images,
        "Gas y refinerias",
        riu_times,
        riu_cats,
        riu_vals,
        _colors_for_fuel_groups([_asignar_grupo(t) for t in riu_cats]),
        output_dir=output_dir,
        title="Refinerias + importaciones - Consumo",
        x_label="A�o",
        y_label="PJ",
    )

    # Sectores
    sector_prefixes = {
        "residencial": "DEMRES",
        "industrial": "DEMIN",
        "transporte": "DEMTRA",
        "terciario": "DEMTER",
        "otros": "DEMCOQ",
    }
    for sector_name, prefix in sector_prefixes.items():
        s_prod = [r for r in prod_rows if r["tech"].upper().startswith(prefix)]
        s_use = [r for r in use_rows if r["tech"].upper().startswith(prefix)]

        sp_times, sp_cats, sp_vals = _build_series(
            s_prod,
            time_getter=lambda r: r["year"],
            category_getter=lambda r: _asignar_grupo(f"{r['tech']}_{r['fuel']}"),
            value_getter=lambda r: r["value"],
            top_n=12,
        )
        _plot_series(
            f"sector_{sector_name}_production_by_year.png",
            section_images,
            "Sectores",
            sp_times,
            sp_cats,
            sp_vals,
            _colors_for_fuel_groups(sp_cats),
            output_dir=output_dir,
            title=f"{sector_name.title()} - Produccion por combustible",
            x_label="A�o",
            y_label="PJ",
        )

        su_times, su_cats, su_vals = _build_series(
            s_use,
            time_getter=lambda r: r["year"],
            category_getter=lambda r: _asignar_grupo(f"{r['tech']}_{r['fuel']}"),
            value_getter=lambda r: r["value"],
            top_n=12,
        )
        _plot_series(
            f"sector_{sector_name}_use_by_year.png",
            section_images,
            "Sectores",
            su_times,
            su_cats,
            su_vals,
            _colors_for_fuel_groups(su_cats),
            output_dir=output_dir,
            title=f"{sector_name.title()} - Consumo por combustible",
            x_label="A�o",
            y_label="PJ",
        )

    html_path = output_dir / "report.html"
    _write_html_report(result, output_path=html_path, section_images=section_images)

    print(f"Reporte HTML: {html_path}")
    print(f"PNGs: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
