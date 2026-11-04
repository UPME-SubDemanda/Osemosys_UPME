"""Construye el SAND PD de 6 TS anidado en el 2 TS día/noche (madrugada 00–06, día 06–18, noche 18–24).

Base: ``tmp/sand/inputs/PD_2TS_41D_2055_SAND_03Jun2026.xlsx``. El método está en
``nest.py``; el escalamiento del uso final, en ``common.py``.

Uso (desde backend/):
  python scripts/sand_6ts/build_pd_6ts_nest.py                # → tmp/sand/outputs/pd_6ts_nest/PD_6TS_NEST.xlsx
  python scripts/sand_6ts/build_pd_6ts_nest.py --flat         # formas planas: debe dar el objetivo del 2 TS
  python scripts/sand_6ts/build_pd_6ts_nest.py --af-div       # AvailabilityFactor ÷ f en el uso final
"""

from __future__ import annotations

from common import INPUTS_DIR, OUTPUTS_DIR
from nest import run_cli_6ts_nest

BASE_SAND = INPUTS_DIR / "PD_2TS_41D_2055_SAND_03Jun2026.xlsx"
OUT_DIR = OUTPUTS_DIR / "pd_6ts_nest"


if __name__ == "__main__":
    run_cli_6ts_nest(__doc__.splitlines()[0], BASE_SAND, OUT_DIR, "PD_6TS_NEST")
