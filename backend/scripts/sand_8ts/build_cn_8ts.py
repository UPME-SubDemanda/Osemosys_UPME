"""Construye el SAND CN de 8 timeslices (6 TS + bloque de punta corto) a partir del CN de 2 TS.

Base: ``tmp/sand/inputs/CN_scenario_166_Parameters_SAND.xlsx``, exportado desde la BD de
la app (escenario 166). El método está en ``common_8ts.py``, que reutiliza el 6 TS
de ``scripts/sand_6ts/common.py``; ver ``docs/sand-8ts-punta.md``.

Como es un export de la BD, omite las filas de CapacityFactor que valen el
default (1); se completan antes de calibrar (``fill_default_capacity_factor``).
Las demandas de hidrógeno propias del CN (EXPHDG, HDGFUR) son
AccumulatedAnnualDemand: no llevan perfil y no cambian con la punta.

Uso (desde backend/):
  python scripts/sand_8ts/build_cn_8ts.py --out ../tmp/sand/outputs/CN_8TS_41D_2055_SAND_20Oct2026.xlsx
  python scripts/sand_8ts/build_cn_8ts.py --peak-hours 2 --peak-ratio 1.35
"""

from __future__ import annotations

from common_8ts import INPUTS_DIR, OUTPUTS_DIR, fill_default_capacity_factor, run_cli_8ts

BASE_SAND = INPUTS_DIR / "CN_scenario_166_Parameters_SAND.xlsx"
OUT_DIR = OUTPUTS_DIR / "cn_8ts"


if __name__ == "__main__":
    run_cli_8ts(__doc__.splitlines()[0], BASE_SAND, OUT_DIR, "CN_8TS_41D_2055_SAND",
                prepare_base=fill_default_capacity_factor)
