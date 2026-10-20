"""Genera las gráficas de la UI (todas las del menú) a partir de corridas CLI.

Las corridas de ``run_osemosys_cli.py excel ... -o tmp/sand/runs/<caso>`` no quedan
en la BD, así que la app no puede graficarlas. Este script reutiliza el motor de
la app (``chart_service.build_chart_data``) con un cargador que lee los CSV de
resultados en lugar de ``osemosys_output_param_value``. El catálogo de gráficas
(configs, filtros, colores, etiquetas) se siembra en una SQLite local desde el
código, igual que lo haría la API al arrancar. Resultado: un JSON con la misma
``ChartDataResponse`` que recibe el frontend, por gráfica y por caso.

Uso (desde backend/):
  python scripts/sand_6ts/ui_charts_from_runs.py 2TS 6TS_CALc 6TS_P115 \
      --out ../tmp/sand/runs/ui_charts.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

from common import REPO_ROOT, RUNS_DIR

CATALOG_DB = RUNS_DIR / "catalog.db"

# La sesión de BD debe apuntar a la SQLite del catálogo antes de importar la app.
os.environ["DATABASE_URL"] = f"sqlite:///{CATALOG_DB}"
os.environ.setdefault("ENVIRONMENT", "local")
sys.path.insert(0, str(REPO_ROOT / "backend"))

import app.models  # noqa: E402,F401  (registra la metadata)
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.visualization import chart_service  # noqa: E402
from app.visualization.catalog_cache import warm_catalog_cache  # noqa: E402
from app.visualization.catalog_seed import seed_visualization_catalog  # noqa: E402

# Variables tipadas: archivo CSV y columna de valor de run_osemosys_cli.
TYPED_FILES = {
    "Dispatch": ("dispatch.csv", "technology_name", "fuel_name", "dispatch"),
    "NewCapacity": ("new_capacity.csv", "technology_name", None, "new_capacity"),
    "UnmetDemand": ("unmet_demand.csv", None, None, "unmet_demand"),
    "AnnualEmissions": ("annual_emissions.csv", None, None, "annual_emissions"),
}
EMPTY = pd.DataFrame(columns=["TECHNOLOGY", "FUEL", "TIMESLICE", "YEAR", "VALUE"])


class CsvRuns:
    """Sustituye la lectura de la BD por los CSV de cada caso (job_id = índice)."""

    def __init__(self, cases: list[str]):
        self.cases = cases
        self._cache: dict[tuple[int, str], pd.DataFrame] = {}

    def load(self, _db, job_id: int, variable_name: str) -> pd.DataFrame:
        key = (job_id, variable_name)
        if key not in self._cache:
            self._cache[key] = self._read(RUNS_DIR / self.cases[job_id], variable_name)
        return self._cache[key].copy()

    @staticmethod
    def _read(case_dir: Path, variable: str) -> pd.DataFrame:
        if variable in TYPED_FILES:
            fname, tech, fuel, value = TYPED_FILES[variable]
            path = case_dir / fname
            if not path.exists():
                return EMPTY.copy()
            d = pd.read_csv(path)
            return pd.DataFrame({
                "TECHNOLOGY": d[tech].fillna("") if tech else "",
                "FUEL": d[fuel].fillna("") if fuel else "",
                "REGION": d.get("region_name", ""),
                "TIMESLICE": "",
                "YEAR": d["year"].astype(int),
                "VALUE": d[value].astype(float),
            })
        path = case_dir / f"{variable}.csv"
        if not path.exists():
            return EMPTY.copy()
        d = pd.read_csv(path)
        if "TECHNOLOGY" in d.columns:  # REGION, TECHNOLOGY, [FUEL, DUMMY=TS], YEAR, VALUE
            return pd.DataFrame({
                "TECHNOLOGY": d["TECHNOLOGY"].astype(str),
                "FUEL": d["FUEL"].astype(str) if "FUEL" in d.columns else "",
                "TIMESLICE": d["DUMMY"].astype(str) if "DUMMY" in d.columns else "",
                "YEAR": d["YEAR"].astype(int),
                "VALUE": d["VALUE"].astype(float),
            })
        # IDX1..IDXn: misma heurística de posiciones que _load_variable_data.
        idx = [c for c in d.columns if c.startswith("IDX")]
        tech = d[idx[1]].astype(str) if len(idx) > 1 else ""
        fuel = d[idx[2]].astype(str) if len(idx) >= 4 else ""
        year = d[idx[-1]]
        return pd.DataFrame({"TECHNOLOGY": tech, "FUEL": fuel, "TIMESLICE": "",
                             "YEAR": year.astype(int), "VALUE": d["VALUE"].astype(float)})

    def max_year(self, _db, job_id: int) -> int | None:
        d = self.load(None, job_id, "TotalCapacityAnnual")
        return int(d["YEAR"].max()) if not d.empty else None


def prepare_catalog():
    CATALOG_DB.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.drop_all(bind=engine)  # catálogo desechable: se siembra desde cero
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_visualization_catalog(db)
    db.commit()
    return db, warm_catalog_cache(db)


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cases", nargs="+", help="Carpetas de corrida dentro de tmp/sand/runs/")
    parser.add_argument("--out", type=Path, default=RUNS_DIR / "ui_charts.json")
    args = parser.parse_args()

    runs = CsvRuns(args.cases)
    chart_service._load_variable_data = runs.load
    chart_service._get_simulation_max_year = runs.max_year
    chart_service._is_regional_job = lambda _db, _job: False

    db, catalog = prepare_catalog()
    modules, charts, errors = [], {}, []
    for module in catalog.menu:
        items = []
        for group in [module] + module.get("subs", []):
            for item in group.get("charts", []):
                tipo = item["tipo"]
                if tipo in charts:
                    continue
                un = "GW" if item.get("is_capacity") else "PJ"
                charts[tipo] = {"label": item["label"], "unit": un, "cases": {}}
                for job_id, case in enumerate(args.cases):
                    try:
                        resp = chart_service.build_chart_data(
                            db, job_id, tipo, un=un, agrupar_por=item.get("default_grouping"))
                        charts[tipo]["cases"][case] = resp.model_dump()
                    except Exception as exc:  # una gráfica que falla no detiene el resto
                        charts[tipo]["cases"][case] = None
                        errors.append(f"{tipo} [{case}]: {type(exc).__name__}: {exc}")
                items.append({"tipo": tipo, "subsector": group.get("label") if group is not module else None})
        modules.append({"label": module["label"], "charts": items})

    args.out.write_text(json.dumps({"cases": args.cases, "modules": modules, "charts": charts},
                                   ensure_ascii=False, separators=(",", ":")))
    ok = sum(1 for c in charts.values() for v in c["cases"].values() if v)
    print(f"{len(charts)} gráficas × {len(args.cases)} casos: {ok} generadas, {len(errors)} con error → {args.out}")
    for e in errors:
        print("  -", e[:200])


if __name__ == "__main__":
    _main()
