"""Construye el SAND PA de 6 TS anidado en el 2 TS día/noche (madrugada 00–06, día 06–18, noche 18–24).

Base: ``tmp/sand/inputs/PA_scenario_167_Parameters_SAND.xlsx``, exportado desde la BD de
la app (escenario 167). El método está en ``nest.py``; el escalamiento del uso final, en
``common.py``. Como es un export de la BD, omite las filas de CapacityFactor que valen el
default (1); se completan antes de anidar, y OIL002 (sin demanda) recibe un perfil
plano (``prepare_nested_db_export``).

Uso (desde backend/):
  python scripts/sand_6ts/build_pa_6ts_nest.py --out ../tmp/sand/outputs/pa_6ts_nest/PA_6TS_NEST_41D_2055_SAND_<fecha>.xlsx
"""

from __future__ import annotations

from common import INPUTS_DIR, OUTPUTS_DIR, prepare_nested_db_export
from nest import run_cli_6ts_nest

BASE_SAND = INPUTS_DIR / "PA_scenario_167_Parameters_SAND.xlsx"
OUT_DIR = OUTPUTS_DIR / "pa_6ts_nest"


if __name__ == "__main__":
    run_cli_6ts_nest(__doc__.splitlines()[0], BASE_SAND, OUT_DIR, "PA_6TS_NEST",
                     prepare_base=prepare_nested_db_export)
