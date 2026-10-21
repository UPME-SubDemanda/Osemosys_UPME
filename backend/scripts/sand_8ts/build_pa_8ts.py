"""Construye el SAND PA de 8 timeslices (6 TS + bloque de punta corto) a partir del PA de 2 TS.

Base: ``tmp/sand/inputs/PA_scenario_167_Parameters_SAND.xlsx``, exportado desde la BD de
la app (escenario 167). El método está en ``common_8ts.py``, que reutiliza el 6 TS
de ``scripts/sand_6ts/common.py``; ver ``docs/sand-8ts-punta.md``.

Como es un export de la BD, omite las filas de CapacityFactor que valen el
default (1); se completan antes de calibrar (``fill_default_capacity_factor``).

Uso (desde backend/):
  python scripts/sand_8ts/build_pa_8ts.py --out ../tmp/sand/outputs/PA_8TS_41D_2055_SAND_20Oct2026.xlsx
  python scripts/sand_8ts/build_pa_8ts.py --peak-hours 2 --peak-ratio 1.35
"""

from __future__ import annotations

from common_8ts import INPUTS_DIR, OUTPUTS_DIR, fill_default_capacity_factor, run_cli_8ts

BASE_SAND = INPUTS_DIR / "PA_scenario_167_Parameters_SAND.xlsx"
OUT_DIR = OUTPUTS_DIR / "pa_8ts"


if __name__ == "__main__":
    run_cli_8ts(__doc__.splitlines()[0], BASE_SAND, OUT_DIR, "PA_8TS_41D_2055_SAND",
                prepare_base=fill_default_capacity_factor)
