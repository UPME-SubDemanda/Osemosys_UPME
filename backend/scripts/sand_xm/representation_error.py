"""Mide con los datos horarios de XM cuánto pierde cada partición de timeslices.

Cada hora se reemplaza por el promedio de su timeslice (estación × bloque del
día), igual que en OSeMOSYS. Se compara contra la serie horaria real:
  - variación conservada (R²): 1 − Σ(x − x̄_TS)² / Σ(x − x̄)²;
  - punta: máximo de los promedios por TS frente a la hora pico real y al
    promedio de las 100 horas más altas;
  - curva de duración: error medio absoluto de la curva ordenada (en % del promedio).
Sobre la demanda y sobre la carga neta (demanda − solar) con la solar escalada a
una participación anual dada, porque eso es lo que debe cubrir el resto del sistema.
La forma solar se normaliza por mes para quitar el crecimiento del parque en 2023–24.

Uso (desde backend/):
  python scripts/sand_xm/representation_error.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from xm_series import load_hourly  # noqa: E402

# Estaciones: mes → etiqueta.
SEASONS = {
    "año": {m: "A" for m in range(1, 13)},
    "semestres": {m: "S1" if m <= 6 else "S2" for m in range(1, 13)},
    "hidro 2": {m: "seca" if m in (12, 1, 2, 3) else "húmeda" for m in range(1, 13)},
    "hidro 4": {**{m: "seca dic–mar" for m in (12, 1, 2, 3)}, **{m: "lluvias abr–may" for m in (4, 5)},
                **{m: "veranillo jun–sep" for m in (6, 7, 8, 9)}, **{m: "lluvias oct–nov" for m in (10, 11)}},
}
# Bloques del día: hora → etiqueta (todos anidados en día 06–18 / noche).
def _blocks(cuts: list[tuple[int, int, str]]) -> dict[int, str]:
    return {h: name for a, b, name in cuts for h in range(a, b)}

BLOCKS = {
    "día/noche": _blocks([(0, 6, "noche"), (6, 18, "día"), (18, 24, "noche")]),
    "3 bloques": _blocks([(0, 6, "madrugada"), (6, 18, "día"), (18, 24, "noche")]),
    "4 bloques": _blocks([(0, 6, "madrugada"), (6, 18, "día"), (18, 21, "punta"), (21, 24, "resto")]),
    # El mediodía 09–16 sigue la meseta solar de XM (≥ 2 veces el promedio diario).
    "6 bloques": _blocks([(0, 6, "madrugada"), (6, 9, "mañana"), (9, 16, "mediodía"), (16, 18, "tarde"),
                          (18, 21, "punta"), (21, 24, "resto")]),
}
# (nombre, estaciones, bloques). Los tres primeros son los del modelo actual.
PARTITIONS = [
    ("2 TS", "año", "día/noche"),
    ("6 TS", "semestres", "3 bloques"),
    ("8 TS", "semestres", "4 bloques"),
    ("8 TS hidro", "hidro 2", "4 bloques"),
    ("12 TS semestres", "semestres", "6 bloques"),
    ("12 TS hidro", "hidro 2", "6 bloques"),
    ("12 TS 4 est.", "hidro 4", "3 bloques"),
    ("16 TS", "hidro 4", "4 bloques"),
    ("24 TS", "hidro 4", "6 bloques"),
    ("Anual × 24 h", "año", None),
]
SOLAR_SHARES = [0.0, 0.10, 0.25]


def labels(idx: pd.DatetimeIndex, season: str, block: str | None) -> pd.Series:
    s = pd.Series(idx.month, index=idx).map(SEASONS[season])
    b = pd.Series(idx.hour, index=idx).map(BLOCKS[block]) if block else pd.Series(idx.hour, index=idx).astype(str)
    return s + "|" + b


def metrics(x: pd.Series, lab: pd.Series) -> dict:
    """R², punta y error de la curva de duración de ``x`` representada por sus promedios por TS."""
    approx = x.groupby(lab).transform("mean")
    sst = ((x - x.mean()) ** 2).sum()
    r2 = 1 - ((x - approx) ** 2).sum() / sst
    top100 = x.nlargest(100).mean()
    dur = np.abs(np.sort(x.to_numpy()) - np.sort(approx.to_numpy())).mean() / x.mean()
    return {"r2": float(r2), "pico": float(approx.max() / x.max()), "top100": float(approx.max() / top100),
            "dur": float(dur)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", type=Path, default=None, help="Escribe los resultados en JSON.")
    args = parser.parse_args()

    df = load_hourly()
    demand = df["demanda"].dropna()
    gen = df.dropna(subset=["solar", "hidro"])
    # Forma solar con promedio 1 en cada mes (quita el crecimiento del parque).
    solar = gen["solar"] / gen["solar"].groupby(gen.index.to_period("M")).transform("mean")
    d_gen = gen["demanda"]
    print(f"Demanda: {demand.index.min():%Y-%m-%d} → {demand.index.max():%Y-%m-%d} ({len(demand)} h)")
    print(f"Solar e hidro: {gen.index.min():%Y-%m-%d} → {gen.index.max():%Y-%m-%d} ({len(gen)} h)")

    out = {"partitions": [], "hydro": {}, "peak_ratio": {}}
    for name, season, block in PARTITIONS:
        n_ts = len(set(SEASONS[season].values())) * (len(set(BLOCKS[block].values())) if block else 24)
        row = {"name": name, "seasons": season, "blocks": block or "24 h", "n_ts": n_ts,
               "demanda": metrics(demand, labels(demand.index, season, block))}
        for share in SOLAR_SHARES[1:]:
            net = d_gen - share * d_gen.mean() * solar
            row[f"neta_{round(share * 100)}"] = metrics(net, labels(net.index, season, block))
        out["partitions"].append(row)

    # Hidro: qué parte de la variación mensual explican las estaciones (generación, no aportes).
    monthly = gen["hidro"].resample("MS").mean()
    monthly = monthly[gen["hidro"].resample("MS").count() > 24 * 20]
    for season in SEASONS:
        lab = pd.Series(monthly.index.month, index=monthly.index).map(SEASONS[season])
        approx = monthly.groupby(lab).transform("mean")
        out["hydro"][season] = float(1 - ((monthly - approx) ** 2).sum() / ((monthly - monthly.mean()) ** 2).sum())

    # Demanda de la punta 18–21 h frente al promedio, por semestre (supuesto del modelo: ×1,30).
    for s in ("S1", "S2"):
        d = demand[pd.Series(demand.index.month, index=demand.index).map(SEASONS["semestres"]) == s]
        out["peak_ratio"][s] = float(d[(d.index.hour >= 18) & (d.index.hour < 21)].mean() / d.mean())

    pd.set_option("display.width", 220)
    rows = []
    for r in out["partitions"]:
        rows.append({"partición": r["name"], "TS": r["n_ts"],
                     "R² dem": r["demanda"]["r2"], "pico dem": r["demanda"]["pico"], "top100 dem": r["demanda"]["top100"],
                     "dur dem %": r["demanda"]["dur"] * 100,
                     "R² neta25": r["neta_25"]["r2"], "pico neta25": r["neta_25"]["pico"],
                     "dur neta25 %": r["neta_25"]["dur"] * 100})
    print(pd.DataFrame(rows).round(3).to_string(index=False))
    print("\nHidro, variación mensual explicada (R²):", {k: round(v, 3) for k, v in out["hydro"].items()})
    print("Punta 18–21 h / promedio:", {k: round(v, 3) for k, v in out["peak_ratio"].items()})
    if args.json:
        args.json.write_text(json.dumps(out, ensure_ascii=False, indent=1))
        print(f"Escrito: {args.json}")


if __name__ == "__main__":
    main()
