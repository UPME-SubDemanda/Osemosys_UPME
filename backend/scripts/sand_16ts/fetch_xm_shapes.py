"""Descarga de XM los perfiles horarios de demanda y solar para el SAND de 16 TS.

Fuente: API pública de XM (``servapibi.xm.com.co``):
  - ``DemaReal`` / ``Sistema``: demanda real horaria del SIN.
  - ``Gene`` / ``Recurso``: generación horaria por recurso; se suman los de
    ``EnerSource = RAD SOLAR`` según ``ListadoRecursos``.

La eólica no se descarga: en XM solo hay 7 recursos eólicos y todos están en
pruebas, así que no hay historia suficiente para una forma (queda plana dentro
de cada bloque del 8 TS).

Las respuestas crudas se guardan en ``tmp/sand/inputs/xm/raw/`` (no se descargan
dos veces). El resultado es el perfil horario típico por semestre, normalizado a
promedio 1 en cada semestre: ``xm_hourly_profiles.csv``, junto a este script
(se versiona para que el build no necesite red). En XM, ``HourNN`` es la hora
que termina en NN: Hour01 = 00–01 h → hora 0.

Semestres: S1 = ene–jun, S2 = jul–dic (supuesto; la UPME usa 185/180 días).

Uso (desde backend/):
  python scripts/sand_16ts/fetch_xm_shapes.py --years 2023 2024
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sand_6ts"))

from common import INPUTS_DIR  # noqa: E402

API = "https://servapibi.xm.com.co"
XM_DIR = INPUTS_DIR / "xm"
RAW_DIR = XM_DIR / "raw"
PROFILES_CSV = Path(__file__).resolve().parent / "xm_hourly_profiles.csv"
SOLAR_SOURCE = "RAD SOLAR"
CHUNK_DAYS = 30  # la API limita las consultas horarias a ~31 días


def _post(endpoint: str, body: dict, cache: Path) -> dict:
    if cache.exists():
        return json.loads(cache.read_text())
    req = urllib.request.Request(
        f"{API}/{endpoint}", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read())
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data))
    return data


def solar_codes() -> set[str]:
    data = _post("lists", {"MetricId": "ListadoRecursos", "Entity": "Sistema"}, XM_DIR / "listado_recursos.json")
    values = [e["Values"] for it in data["Items"] for e in it["ListEntities"]]
    return {v["Code"] for v in values if v.get("EnerSource") == SOLAR_SOURCE}


def hourly(metric: str, entity: str, start: date, end: date) -> pd.DataFrame:
    """Serie horaria larga (fecha, código, hora 0–23, valor), descargada por tramos."""
    rows = []
    cur = start
    while cur <= end:
        stop = min(cur + timedelta(days=CHUNK_DAYS - 1), end)
        body = {"MetricId": metric, "StartDate": cur.isoformat(), "EndDate": stop.isoformat(), "Entity": entity}
        data = _post("hourly", body, RAW_DIR / f"{metric}_{entity}_{cur}_{stop}.json")
        for item in data["Items"]:
            for ent in item["HourlyEntities"]:
                v = ent["Values"]
                for h in range(24):
                    val = v.get(f"Hour{h + 1:02d}")
                    if val not in (None, ""):
                        rows.append((item["Date"], v["code"], h, float(val)))
        print(f"  {metric} {cur} → {stop}", flush=True)
        cur = stop + timedelta(days=1)
    df = pd.DataFrame(rows, columns=["fecha", "codigo", "hora", "valor"])
    df["semestre"] = pd.to_datetime(df["fecha"]).dt.month.map(lambda m: "S1" if m <= 6 else "S2")
    return df


def typical_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Promedio por semestre y hora del total del día, normalizado a promedio 1 por semestre."""
    total = df.groupby(["semestre", "fecha", "hora"])["valor"].sum().reset_index()
    prof = total.groupby(["semestre", "hora"])["valor"].mean().unstack("hora")
    return prof.div(prof.mean(axis=1), axis=0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--years", type=int, nargs="+", default=[2023, 2024])
    args = parser.parse_args()
    start, end = date(min(args.years), 1, 1), date(max(args.years), 12, 31)

    demand = typical_profile(hourly("DemaReal", "Sistema", start, end))
    gen = hourly("Gene", "Recurso", start, end)
    solar = typical_profile(gen[gen["codigo"].isin(solar_codes())])

    out = pd.DataFrame({
        "semestre": [s for s in demand.index for _ in range(24)],
        "hora": list(range(24)) * len(demand.index),
        "demanda": demand.to_numpy().ravel(),
        "solar": solar.loc[demand.index].to_numpy().ravel(),
    })
    out.round(6).to_csv(PROFILES_CSV, index=False)

    pd.set_option("display.width", 250)
    print(f"\nPerfiles {start.year}–{end.year} (promedio = 1 por semestre):")
    print(out.pivot(index="hora", columns="semestre", values=["demanda", "solar"]).round(3).to_string())
    for s in demand.index:
        d = demand.loc[s]
        print(f"{s}: punta 18–21 h = ×{d[18:21].mean():.3f} · hora pico {d.idxmax()} h = ×{d.max():.3f}")
    print(f"\nEscrito: {PROFILES_CSV}")


if __name__ == "__main__":
    main()
