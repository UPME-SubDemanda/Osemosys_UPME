"""Construye el SAND PD de 6 timeslices a partir del PD de 2 TS.

Base: ``tmp/sand/inputs/PD_2TS_41D_2055_SAND_03Jun2026.xlsx`` (completo, S101 = día y
S102 = noche, 12 h cada uno). El método está en ``common.py``; ver
``docs/sand-6ts-migracion.md``.

Uso (desde backend/):
  python scripts/sand_6ts/build_pd_6ts.py --out ../tmp/sand/outputs/PD_6TS_41D_2055_SAND_19Oct2026.xlsx
  python scripts/sand_6ts/build_pd_6ts.py --peak-ratio 1.15
  python scripts/sand_6ts/build_pd_6ts.py --variant upme
"""

from __future__ import annotations

from common import INPUTS_DIR, OUTPUTS_DIR, run_cli

BASE_SAND = INPUTS_DIR / "PD_2TS_41D_2055_SAND_03Jun2026.xlsx"
OUT_DIR = OUTPUTS_DIR / "pd_6ts"


if __name__ == "__main__":
    run_cli(__doc__.splitlines()[0], BASE_SAND, OUT_DIR, "PD_6TS_41D_2055_SAND")
