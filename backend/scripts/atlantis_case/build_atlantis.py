"""Convierte el caso de entrenamiento Atlantis (MathProg) a SAND y a referencias.

Fuente: ``cases/atlantis/source/atlantis.txt`` (repo oficial OSeMOSYS/OSeMOSYS,
``Training_Case_Studies/atlantis.txt``) y ``cases/atlantis/source/osemosys.txt``
(OSeMOSYS/OSeMOSYS_GNU_MathProg, ``src/osemosys.txt``).

Para cada nivel de la escalera de timeslices (1, 2 y 6 TS) produce:
  - ``SAND/atlantis/ATLANTIS_<n>TS[_variante]_SAND.xlsx``: entrada para el
    backend UPME (hoja ``Parameters``), con todo explícito.
  - ``cases/atlantis/reference/atlantis_<n>TS[_variante].dat``: el mismo caso
    agregado en MathProg, para resolverlo con el modelo oficial.
  - Con ``--solve-reference``: glpsol traduce a MPS (``out/atlantis/``) y HiGHS
    resuelve; el objetivo queda en ``cases/atlantis/reference/objectives.json``.

Agregación de timeslices:
  - 1 TS: todo en ``ALL``.
  - 2 TS: ``DAY`` = ID+SD+WD, ``NIGHT`` = IN+SN+WN.
  - 6 TS: el original.
  YearSplit y SpecifiedDemandProfile se suman; CapacityFactor se promedia
  ponderado por YearSplit.

Variantes:
  - ``--no-storage``: sin el almacenamiento DAM (obligatorio en 1 y 2 TS por
    ahora; el import SAND no crea SEASON/DAYTYPE/DAILYTIMEBRACKET).
  - ``--no-re``: REMinProductionTarget = 0 (el modelo UPME no tiene RE2-RE4).

Uso (desde backend/ con el venv activo):
  python scripts/atlantis_case/build_atlantis.py --ts 1 --solve-reference
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
CASE_DIR = REPO_ROOT / "cases" / "atlantis"
SOURCE_DATA = CASE_DIR / "source" / "atlantis.txt"
SOURCE_MODEL = CASE_DIR / "source" / "osemosys.txt"
REFERENCE_DIR = CASE_DIR / "reference"
SAND_DIR = REPO_ROOT / "SAND" / "atlantis"
MPS_DIR = REPO_ROOT / "out" / "atlantis"

# Ausente en atlantis.txt pero exigido por el osemosys.txt actual.
EXTRA_PARAMS = {"DiscountRateStorage": 0.05}

TS_GROUPS: dict[int, dict[str, list[str]]] = {
    1: {"ALL": ["ID", "IN", "SD", "SN", "WD", "WN"]},
    2: {"DAY": ["ID", "SD", "WD"], "NIGHT": ["IN", "SN", "WN"]},
    6: {ts: [ts] for ts in ["ID", "IN", "SD", "SN", "WD", "WN"]},
}

STORAGE_PARAMS = {
    "DaySplit", "Conversionls", "Conversionld", "Conversionlh", "DaysInDayType",
    "TechnologyToStorage", "TechnologyFromStorage", "StorageLevelStart",
    "StorageMaxChargeRate", "StorageMaxDischargeRate", "MinStorageCharge",
    "OperationalLifeStorage", "CapitalCostStorage", "ResidualStorageCapacity",
    "DiscountRateStorage",
}

# Columnas SAND (mismo orden que el generador de Dummylandia).
SAND_DIM_COLUMNS = [
    "REGION", "TECHNOLOGY", "EMISSION", "MODE_OF_OPERATION", "FUEL",
    "TIMESLICE", "STORAGE", "REGION2",
]
SCALAR_COLUMN = "Time indipendent variables"
SPARSE_DIMS = {"FUEL", "EMISSION"}


# ---------------------------------------------------------------------------
# Lectura del data file MathProg
# ---------------------------------------------------------------------------

@dataclass
class Param:
    name: str
    dims: list[str]
    default: float
    values: dict[tuple[str, ...], float] = field(default_factory=dict)

    def get(self, key: tuple[str, ...]) -> float:
        return self.values.get(key, self.default)


@dataclass
class Case:
    sets: dict[str, list[str]]
    params: dict[str, Param]


def read_param_dims(model_path: Path) -> dict[str, list[str]]:
    """Dimensiones de cada parámetro según su declaración en osemosys.txt."""
    dims: dict[str, list[str]] = {}
    for m in re.finditer(r"^param\s+(\w+)\s*(\{([^}]*)\})?", model_path.read_text(), re.M):
        name, body = m.group(1), m.group(3)
        if body is None:
            dims[name] = []
            continue
        dims[name] = [
            part.split(" in ")[1].split(":")[0].strip()
            for part in body.split(",")
            if " in " in part
        ]
    return dims


def _tokens(text: str) -> list[str]:
    text = re.sub(r"#.*", "", text)
    text = text.replace(":=", " := ").replace("]:", "] : ")
    return text.split()


def read_case(data_path: Path, model_path: Path) -> Case:
    """Lee los formatos MathProg que usa atlantis.txt: listas de sets,
    tablas 2D (``param X default d : cols := filas``) y tablas con slice
    (``[a,b,*,*]: cols := filas``)."""
    all_dims = read_param_dims(model_path)
    text = data_path.read_text()
    sets: dict[str, list[str]] = {}
    params: dict[str, Param] = {}

    for stmt in text.split(";"):
        tok = _tokens(stmt)
        if not tok or tok[0] == "end":
            continue
        if tok[0] == "set":
            sets[tok[1]] = tok[3:]
            continue
        if tok[0] != "param":
            raise ValueError(f"Sentencia no soportada: {' '.join(tok[:5])}")
        name = tok[1]
        default = float(tok[3]) if tok[2] == "default" else 0.0
        i = 4 if tok[2] == "default" else 2
        param = Param(name, all_dims[name], default)
        params[name] = param
        if tok[i] == ":":
            # Tabla 2D sin slice: filas = primera dimensión, columnas = segunda.
            i = _read_table(tok, i + 1, ["*"] * len(param.dims), param)
        else:
            assert tok[i] == ":=", stmt
            i += 1
        while i < len(tok):
            if tok[i].startswith("["):
                slice_ = tok[i].strip("[]").split(",")
                assert tok[i + 1] == ":", stmt
                i = _read_table(tok, i + 2, slice_, param)
            else:
                raise ValueError(f"{name}: formato no soportado cerca de {tok[i:i+5]}")
    return Case(sets, params)


def _read_table(tok: list[str], i: int, slice_: list[str], param: Param) -> int:
    free = [k for k, s in enumerate(slice_) if s == "*"]
    assert len(free) == 2, (param.name, slice_)
    cols = []
    while tok[i] != ":=":
        cols.append(tok[i])
        i += 1
    i += 1
    while i < len(tok) and not tok[i].startswith("["):
        row, vals = tok[i], tok[i + 1:i + 1 + len(cols)]
        for col, val in zip(cols, vals):
            key = list(slice_)
            key[free[0]], key[free[1]] = row, col
            param.values[tuple(key)] = float(val)
        i += 1 + len(cols)
    return i


# ---------------------------------------------------------------------------
# Variantes: agregación de timeslices, sin almacenamiento, sin meta RE
# ---------------------------------------------------------------------------

def make_variant(base: Case, n_ts: int, *, storage: bool, re_target: bool) -> Case:
    groups = TS_GROUPS[n_ts]
    old_to_new = {old: new for new, olds in groups.items() for old in olds}
    years = base.sets["YEAR"]
    ys = base.params["YearSplit"]

    sets = {k: list(v) for k, v in base.sets.items()}
    sets["TIMESLICE"] = list(groups)
    params: dict[str, Param] = {}

    for name, p in base.params.items():
        q = Param(name, p.dims, p.default)
        params[name] = q
        if "TIMESLICE" not in p.dims:
            q.values = dict(p.values)
            continue
        li = p.dims.index("TIMESLICE")
        if name in ("YearSplit", "SpecifiedDemandProfile"):
            for key, val in p.values.items():
                new = key[:li] + (old_to_new[key[li]],) + key[li + 1:]
                q.values[new] = q.values.get(new, 0.0) + val
        elif name == "CapacityFactor":
            # Promedio ponderado por YearSplit, sobre el dominio completo
            # (el default 1 cuenta en los timeslices sin dato).
            yi = p.dims.index("YEAR")
            stems = {k[:li] + k[li + 1:] for k in p.values}
            for stem in stems:
                for new, olds in groups.items():
                    y = stem[yi - 1 if yi > li else yi]
                    num = sum(p.get(stem[:li] + (o,) + stem[li:]) * ys.get((o, y)) for o in olds)
                    den = sum(ys.get((o, y)) for o in olds)
                    q.values[stem[:li] + (new,) + stem[li:]] = num / den
        elif name.startswith("Conversion"):
            if n_ts == 6:
                q.values = dict(p.values)
        elif p.values:
            raise NotImplementedError(f"Agregación no definida para {name}")

    if n_ts != 6:
        # Estructura temporal mínima coherente con los nuevos timeslices.
        lh = {"ALL": "1", "DAY": "1", "NIGHT": "2"}
        sets["SEASON"], sets["DAYTYPE"] = ["1"], ["1"]
        sets["DAILYTIMEBRACKET"] = sorted(set(lh[t] for t in groups))
        params["Conversionls"].values = {(t, "1"): 1.0 for t in groups}
        params["Conversionld"].values = {(t, "1"): 1.0 for t in groups}
        params["Conversionlh"].values = {(t, lh[t]): 1.0 for t in groups}

    if not storage:
        sets["STORAGE"] = []
        for name in STORAGE_PARAMS & params.keys():
            if "STORAGE" in params[name].dims:
                params[name].values = {}

    if not re_target:
        params["REMinProductionTarget"].values = {}
        params["REMinProductionTarget"].default = 0.0

    for name, val in EXTRA_PARAMS.items():
        if name not in params:
            dims = read_param_dims(SOURCE_MODEL)[name]
            params[name] = Param(name, dims, val)

    for y in years:
        total = sum(params["YearSplit"].get((t, y)) for t in sets["TIMESLICE"])
        assert abs(total - 1.0) < 1e-3, (y, total)
    return Case(sets, params)


def variant_tag(n_ts: int, storage: bool, re_target: bool) -> str:
    tag = f"{n_ts}TS"
    if not storage:
        tag += "_NOSTO"
    if not re_target:
        tag += "_NORE"
    return tag


# ---------------------------------------------------------------------------
# Escritura MathProg (referencia)
# ---------------------------------------------------------------------------

def _fmt(v: float) -> str:
    return repr(float(v)) if v != int(v) else str(int(v))


def write_dat(case: Case, path: Path) -> Path:
    lines = ["# Generado por backend/scripts/atlantis_case/build_atlantis.py", ""]
    for name, members in case.sets.items():
        lines.append(f"set {name} := {' '.join(members)} ;")
    lines.append("")
    for name, p in case.params.items():
        lines.append(f"param {name} default {_fmt(p.default)} :=")
        for key, val in p.values.items():
            lines.append(f"{' '.join(key)} {_fmt(val)}")
        lines.append(";")
    lines += ["", "end;", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))
    return path


def solve_reference(dat_path: Path, mps_path: Path) -> dict:
    import highspy

    mps_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["glpsol", "-m", str(SOURCE_MODEL), "-d", str(dat_path), "--check",
         "--wfreemps", str(mps_path)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 or not mps_path.exists():
        raise RuntimeError(f"glpsol falló:\n{proc.stdout[-2000:]}\n{proc.stderr}")
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    h.readModel(str(mps_path))
    h.run()
    return {
        "status": h.modelStatusToString(h.getModelStatus()),
        "objective": h.getInfo().objective_function_value,
        "rows": h.getNumRow(),
        "cols": h.getNumCol(),
    }


# ---------------------------------------------------------------------------
# Escritura SAND (entrada UPME)
# ---------------------------------------------------------------------------

def _upme_default(name: str) -> float | None:
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from app.simulation.core.osemosys_defaults import OSEMOSYS_PARAM_DEFAULTS

    return OSEMOSYS_PARAM_DEFAULTS.get(name.lower())


def build_sand(case: Case) -> pd.DataFrame:
    """Una fila por combinación de índices no-YEAR.

    Parámetros sin FUEL/EMISSION se escriben sobre su dominio completo. Los
    que sí los tienen, solo con valores distintos del default de Atlantis,
    salvo que ese default difiera del de la UPME (entonces, dominio completo).
    """
    years = case.sets["YEAR"]
    columns = ["Parameter"] + SAND_DIM_COLUMNS + [SCALAR_COLUMN] + years
    rows = []
    for name, p in case.params.items():
        if name in STORAGE_PARAMS or name in EXTRA_PARAMS:
            continue
        upme_default = _upme_default(name)
        if upme_default is None:
            continue
        key_dims = [d for d in p.dims if d != "YEAR"]
        has_year = "YEAR" in p.dims
        full = not (SPARSE_DIMS & set(key_dims)) or upme_default != p.default
        if full:
            keys = list(itertools.product(*(case.sets[d] for d in key_dims)))
        else:
            yi = p.dims.index("YEAR") if has_year else None
            keys = sorted({
                k[:yi] + k[yi + 1:] if has_year else k
                for k, v in p.values.items() if v != p.default
            })
        for key in keys:
            row = dict.fromkeys(columns)
            row["Parameter"] = name
            row.update(zip(key_dims, key))
            if has_year:
                yi = p.dims.index("YEAR")
                for y in years:
                    row[y] = p.get(key[:yi] + (y,) + key[yi:])
            else:
                row[SCALAR_COLUMN] = p.get(key)
            rows.append(row)
    df = pd.DataFrame(rows, columns=columns)
    df.columns = [int(c) if c in years else c for c in df.columns]
    return df


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ts", type=int, choices=sorted(TS_GROUPS), default=1)
    parser.add_argument("--no-storage", action="store_true")
    parser.add_argument("--no-re", action="store_true")
    parser.add_argument("--solve-reference", action="store_true")
    args = parser.parse_args()

    storage = not args.no_storage
    if storage and args.ts != 6:
        parser.error("Por ahora el almacenamiento solo está definido para 6 TS (usar --no-storage).")

    base = read_case(SOURCE_DATA, SOURCE_MODEL)
    case = make_variant(base, args.ts, storage=storage, re_target=not args.no_re)
    tag = variant_tag(args.ts, storage, not args.no_re)

    dat = write_dat(case, REFERENCE_DIR / f"atlantis_{tag}.dat")
    print(f"Referencia MathProg: {dat}")

    if not storage:  # el SAND no admite almacenamiento (ver docstring)
        df = build_sand(case)
        SAND_DIR.mkdir(parents=True, exist_ok=True)
        xlsx = SAND_DIR / f"ATLANTIS_{tag}_SAND.xlsx"
        df.to_excel(xlsx, sheet_name="Parameters", index=False)
        print(f"SAND: {xlsx}  ({len(df)} filas, {df['Parameter'].nunique()} parámetros)")

    if args.solve_reference:
        res = solve_reference(dat, MPS_DIR / f"atlantis_{tag}.mps")
        print(f"Referencia {tag}: {res['status']}  objetivo = {res['objective']:.6f}  "
              f"({res['rows']} filas, {res['cols']} columnas)")
        obj_path = REFERENCE_DIR / "objectives.json"
        data = json.loads(obj_path.read_text()) if obj_path.exists() else {}
        data[tag] = res
        obj_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    _main()
