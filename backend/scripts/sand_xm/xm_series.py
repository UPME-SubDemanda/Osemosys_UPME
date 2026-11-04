"""Series horarias de XM ya descargadas (no usa la red): demanda del SIN y generación solar e hidro.

Lee las respuestas crudas que dejó ``scripts/sand_16ts/fetch_xm_shapes.py`` en
``tmp/sand/inputs/xm/raw/``. En XM, ``HourNN`` es la hora que termina en NN
(Hour01 = 00–01 h → hora 0). La generación viene en kWh por recurso; se agrupa
por ``EnerSource`` del listado de recursos (``RAD SOLAR``, ``AGUA``).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sand_6ts"))

from common import INPUTS_DIR  # noqa: E402

XM_DIR = INPUTS_DIR / "xm"
RAW_DIR = XM_DIR / "raw"
SOURCES = {"RAD SOLAR": "solar", "AGUA": "hidro"}


def _sources() -> dict[str, str]:
    data = json.loads((XM_DIR / "listado_recursos.json").read_text())
    values = [e["Values"] for it in data["Items"] for e in it["ListEntities"]]
    return {v["Code"]: SOURCES[v["EnerSource"]] for v in values if v.get("EnerSource") in SOURCES}


def _read(prefix: str, codes: dict[str, str] | None) -> pd.DataFrame:
    """Serie larga (timestamp, grupo, MWh) de todos los archivos ``prefix_*.json``."""
    rows = []
    for path in sorted(RAW_DIR.glob(f"{prefix}_*.json")):
        for item in json.loads(path.read_text())["Items"]:
            day = pd.Timestamp(item["Date"])
            for ent in item["HourlyEntities"]:
                v = ent["Values"]
                group = "demanda" if codes is None else codes.get(v["code"])
                if group is None:
                    continue
                for h in range(24):
                    val = v.get(f"Hour{h + 1:02d}")
                    if val not in (None, ""):
                        rows.append((day + pd.Timedelta(hours=h), group, float(val) / 1e3))
    return pd.DataFrame(rows, columns=["t", "grupo", "mwh"])


def load_hourly() -> pd.DataFrame:
    """DataFrame horario indexado por timestamp: demanda, solar, hidro (MWh); NaN donde no hay datos."""
    dem = _read("DemaReal_Sistema", None)
    gen = _read("Gene_Recurso", _sources())
    df = pd.concat([dem, gen]).groupby(["t", "grupo"])["mwh"].sum().unstack("grupo")
    # XM omite las horas en cero (la solar de noche): dentro del periodo con datos de
    # generación son cero; fuera de él quedan NaN.
    covered = df.index.isin(gen["t"].drop_duplicates())
    df.loc[covered, ["solar", "hidro"]] = df.loc[covered, ["solar", "hidro"]].fillna(0.0)
    df.loc[~covered, ["solar", "hidro"]] = float("nan")
    return df.sort_index()
