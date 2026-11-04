"""Construye el SAND PA de 8 TS anidado en el 2 TS (6 TS anidado + punta 18–21 h dentro de la noche).

Base: ``tmp/sand/inputs/PA_scenario_167_Parameters_SAND.xlsx``, exportado desde la BD de
la app (escenario 167). Bloques por semestre: madrugada 00–06, día 06–18, punta 18–21
(×1,16, medida en XM) y resto 21–24. El método está en ``common_8ts.py``
(``run_cli_8ts_nest``) y ``scripts/sand_6ts/nest.py``. Los CF omitidos por el export
(default 1) se completan antes de anidar, y OIL002 (sin demanda) recibe un perfil
plano (``prepare_nested_db_export``).

Uso (desde backend/):
  python scripts/sand_8ts/build_pa_8ts_nest.py --out ../tmp/sand/outputs/pa_8ts_nest/PA_8TS_NEST_PB3H116_41D_2055_SAND_<fecha>.xlsx
"""

from __future__ import annotations

from common_8ts import INPUTS_DIR, OUTPUTS_DIR, prepare_nested_db_export, run_cli_8ts_nest

BASE_SAND = INPUTS_DIR / "PA_scenario_167_Parameters_SAND.xlsx"
OUT_DIR = OUTPUTS_DIR / "pa_8ts_nest"


if __name__ == "__main__":
    run_cli_8ts_nest(__doc__.splitlines()[0], BASE_SAND, OUT_DIR, "PA_8TS_NEST",
                     prepare_base=prepare_nested_db_export)
