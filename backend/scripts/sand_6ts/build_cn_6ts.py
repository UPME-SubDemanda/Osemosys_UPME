"""Construye el SAND CN de 6 timeslices a partir del CN de 2 TS.

Base: ``tmp/sand/inputs/CN_scenario_166_Parameters_SAND.xlsx``, exportado desde la BD de
la app (escenario 166, S101/S102 de 12 h). El método está en ``common.py``;
ver ``docs/sand-6ts-migracion.md``.

Como es un export de la BD, omite las filas de CapacityFactor que valen el
default (1); se completan antes de calibrar (``fill_default_capacity_factor``).
Las demandas de hidrógeno propias del CN (EXPHDG, HDGFUR) son
AccumulatedAnnualDemand: no llevan perfil y no cambian con los 6 TS.

Uso (desde backend/):
  python scripts/sand_6ts/build_cn_6ts.py --out ../tmp/sand/outputs/CN_6TS_41D_2055_SAND_19Oct2026.xlsx
"""

from __future__ import annotations

from common import INPUTS_DIR, OUTPUTS_DIR, fill_default_capacity_factor, run_cli

BASE_SAND = INPUTS_DIR / "CN_scenario_166_Parameters_SAND.xlsx"
OUT_DIR = OUTPUTS_DIR / "cn_6ts"


if __name__ == "__main__":
    run_cli(__doc__.splitlines()[0], BASE_SAND, OUT_DIR, "CN_6TS_41D_2055_SAND",
            prepare_base=fill_default_capacity_factor)
