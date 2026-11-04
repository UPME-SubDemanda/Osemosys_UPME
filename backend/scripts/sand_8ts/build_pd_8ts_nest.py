"""Construye el SAND PD de 8 TS anidado en el 2 TS (6 TS anidado + punta 18–21 h dentro de la noche).

Base: ``tmp/sand/inputs/PD_2TS_41D_2055_SAND_03Jun2026.xlsx``. Bloques por semestre:
madrugada 00–06, día 06–18, punta 18–21 (×1,16, medida en XM) y resto 21–24. El método está en
``common_8ts.py`` (``run_cli_8ts_nest``) y ``scripts/sand_6ts/nest.py``.

Uso (desde backend/):
  python scripts/sand_8ts/build_pd_8ts_nest.py                    # → tmp/sand/outputs/pd_8ts_nest/PD_8TS_NEST_PB3H116.xlsx
  python scripts/sand_8ts/build_pd_8ts_nest.py --peak-ratio 1.30  # punta supuesta anterior
  python scripts/sand_8ts/build_pd_8ts_nest.py --flat             # formas planas: debe dar el objetivo del 2 TS
"""

from __future__ import annotations

from common_8ts import INPUTS_DIR, OUTPUTS_DIR, run_cli_8ts_nest

BASE_SAND = INPUTS_DIR / "PD_2TS_41D_2055_SAND_03Jun2026.xlsx"
OUT_DIR = OUTPUTS_DIR / "pd_8ts_nest"


if __name__ == "__main__":
    run_cli_8ts_nest(__doc__.splitlines()[0], BASE_SAND, OUT_DIR, "PD_8TS_NEST")
