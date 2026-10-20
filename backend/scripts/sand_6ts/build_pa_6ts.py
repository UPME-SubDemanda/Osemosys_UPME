"""Construye el SAND PA de 6 timeslices a partir del PA de 2 TS.

Base: ``tmp/sand/inputs/PA_scenario_167_Parameters_SAND.xlsx``, exportado desde la BD de
la app (escenario 167, S101/S102 de 12 h). El método está en ``common.py``;
ver ``docs/sand-6ts-migracion.md``.

Como es un export de la BD, omite las filas de CapacityFactor que valen el
default (1); se completan antes de calibrar (``fill_default_capacity_factor``).

Uso (desde backend/):
  python scripts/sand_6ts/build_pa_6ts.py --out ../tmp/sand/outputs/PA_6TS_41D_2055_SAND_19Oct2026.xlsx
"""

from __future__ import annotations

from common import INPUTS_DIR, OUTPUTS_DIR, fill_default_capacity_factor, run_cli

BASE_SAND = INPUTS_DIR / "PA_scenario_167_Parameters_SAND.xlsx"
OUT_DIR = OUTPUTS_DIR / "pa_6ts"


if __name__ == "__main__":
    run_cli(__doc__.splitlines()[0], BASE_SAND, OUT_DIR, "PA_6TS_41D_2055_SAND",
            prepare_base=fill_default_capacity_factor)
