"""Construye el SAND PD de 8 timeslices (6 TS + bloque de punta corto) a partir del PD de 2 TS.

Base: ``tmp/sand/inputs/PD_2TS_41D_2055_SAND_03Jun2026.xlsx``. El método está en
``common_8ts.py``, que reutiliza el 6 TS de ``scripts/sand_6ts/common.py``; ver
``docs/sand-8ts-punta.md``.

Uso (desde backend/):
  python scripts/sand_8ts/build_pd_8ts.py                     # punta 3 h × 1,30
  python scripts/sand_8ts/build_pd_8ts.py --out ../tmp/sand/outputs/PD_8TS_41D_2055_SAND_20Oct2026.xlsx
  python scripts/sand_8ts/build_pd_8ts.py --peak-hours 2 --peak-ratio 1.35
"""

from __future__ import annotations

from common_8ts import INPUTS_DIR, OUTPUTS_DIR, run_cli_8ts

BASE_SAND = INPUTS_DIR / "PD_2TS_41D_2055_SAND_03Jun2026.xlsx"
OUT_DIR = OUTPUTS_DIR / "pd_8ts"


if __name__ == "__main__":
    run_cli_8ts(__doc__.splitlines()[0], BASE_SAND, OUT_DIR, "PD_8TS_41D_2055_SAND")
