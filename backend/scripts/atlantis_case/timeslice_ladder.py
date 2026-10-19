"""Escalera de timeslices para Atlantis: tiempo de ejecución y convergencia del costo.

Desagrega los 6 timeslices de Atlantis (variante sin almacenamiento y sin meta
RE, la que la UPME resuelve igual que el OSeMOSYS oficial) en perfiles horarios
sintéticos, los vuelve a agregar a cada nivel y corre UPME y referencia.

Perfiles sintéticos (calibrados): dentro de cada bloque original (WD, WN, ID,
IN, SD, SN) la suma de YearSplit y de SpecifiedDemandProfile, y el promedio de
CapacityFactor ponderado por YearSplit, son exactamente los de Atlantis. Por
eso el nivel de 6 TS reproduce el caso original. Dentro del bloque se reparten
con formas típicas: demanda por sector (picos de mañana/tarde, fin de semana),
solar en campana, eólica variable con ciclo diario, hidro por mes.

Calendario supuesto (Atlantis no lo define): invierno oct–mar, intermedia
abr–jun, verano jul–sep; día = 06–22 h, noche = 22–06 h; meses iguales.

Uso (desde backend/):
  python scripts/atlantis_case/timeslice_ladder.py --levels L006 L012 L024
  python scripts/atlantis_case/timeslice_ladder.py --levels all --timeout 1800
"""

from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_atlantis import (  # noqa: E402
    REPO_ROOT, SOURCE_DATA, SOURCE_MODEL, Case, Param, build_sand,
    make_variant, read_case, write_dat,
)

LADDER_DIR = REPO_ROOT / "out" / "atlantis" / "ladder"
RESULTS = REPO_ROOT / "cases" / "atlantis" / "reference" / "ladder_results.json"

SEASON_MONTHS = {"W": [10, 11, 12, 1, 2, 3], "I": [4, 5, 6], "S": [7, 8, 9]}
MONTH_SEASON = {m: s for s, ms in SEASON_MONTHS.items() for m in ms}

# Particiones del día alineadas con los bordes 06 h y 22 h: (hora_ini, hora_fin).
PARTITIONS = {
    2: [(22, 30), (6, 22)],
    4: [(22, 30), (6, 11), (11, 17), (17, 22)],
    8: [(22, 26), (26, 30), (6, 9), (9, 12), (12, 15), (15, 18), (18, 20), (20, 22)],
    12: [(h, h + 2) for h in range(0, 24, 2)],
    24: [(h, h + 1) for h in range(24)],
}
DAYTYPES = {"A": [("A", 1.0)], "KE": [("K", 5 / 7), ("E", 2 / 7)]}


@dataclass(frozen=True)
class Level:
    name: str
    months: bool       # False: 3 temporadas; True: 12 meses
    daytypes: str      # "A" (todos iguales) o "KE" (laborable / fin de semana)
    blocks: int        # bloques por día (clave de PARTITIONS)

    @property
    def n_ts(self) -> int:
        return (12 if self.months else 3) * len(DAYTYPES[self.daytypes]) * self.blocks


LEVELS = [
    Level("L006", False, "A", 2),
    Level("L012", False, "A", 4),
    Level("L024", False, "A", 8),
    Level("L036", False, "A", 12),
    Level("L072", False, "A", 24),
    Level("L144", True, "A", 12),
    Level("L288", True, "A", 24),
    Level("L576", True, "KE", 24),
]
LEVELS_BY_NAME = {lv.name: lv for lv in LEVELS}


# ---------------------------------------------------------------------------
# Formas horarias sintéticas (hora 0-23, mes 1-12, tipo de día K/E/A)
# ---------------------------------------------------------------------------

def _bump(h: float, center: float, width: float) -> float:
    return math.exp(-0.5 * ((h - center) / width) ** 2)


def demand_shape(fuel: str, h: int, month: int, dt: str) -> float:
    if fuel == "EL_Residential":
        v = 0.5 + 0.35 * _bump(h, 8, 1.5) + 0.9 * _bump(h, 19.5, 2.0)
        v *= 1 + 0.10 * math.cos(2 * math.pi * (month - 1) / 12)  # más en enero
        weekend = 1.08
    elif fuel == "EL_Services":
        v = 0.25 + 1.0 * (1 / (1 + math.exp(-(h - 8))) - 1 / (1 + math.exp(-(h - 18))))
        v *= 1 + 0.08 * math.cos(2 * math.pi * (month - 7) / 12)  # más en julio (frío/calor)
        weekend = 0.6
    elif fuel == "EL_Transport":
        v = 0.3 + 0.8 * _bump(h, 7.5, 1.2) + 0.7 * _bump(h, 17.5, 1.5)
        weekend = 0.75
    else:  # EL_Industry
        v = 0.85 + 0.15 * (1 if 7 <= h < 19 else 0)
        weekend = 0.7
    return v * (weekend if dt == "E" else 1.0)


def solar_shape(h: int, month: int, sunset: float = 19.0) -> float:
    sunrise = 6.0
    x = (h + 0.5 - sunrise) / (sunset - sunrise)
    v = math.sin(math.pi * x) if 0 < x < 1 else 0.0
    return v * (1 + 0.15 * math.cos(2 * math.pi * (month - 7) / 12))


def _wind_series() -> dict[tuple[int, str], list[float]]:
    """AR(1) determinista por (mes, tipo de día) con ciclo diario (más de noche)."""
    rng = random.Random(42)
    out = {}
    for month in range(1, 13):
        for dt in ("A", "K", "E"):
            x, vals = 0.0, []
            for h in range(24):
                x = 0.8 * x + rng.gauss(0, 0.35)
                diurnal = 1 + 0.25 * math.cos(2 * math.pi * (h - 2) / 24)
                vals.append(max(0.05, diurnal * (1 + x)))
            out[(month, dt)] = vals
    return out


WIND = _wind_series()


def cf_shape(tech: str, h: int, month: int, dt: str) -> float:
    if tech in ("PV_UTL", "PV_ROF"):
        return solar_shape(h, month)
    if tech == "CSP":
        return solar_shape(h, month, sunset=21.0)  # algo de almacenamiento térmico
    if tech == "WIND":
        return WIND[(month, dt)][h]
    if tech in ("HYDRO_DAM", "HYDRO_MIN"):
        return 1 + 0.15 * math.sin(2 * math.pi * (month - 3) / 12)
    return 1.0


# ---------------------------------------------------------------------------
# Desagregación calibrada
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Slot:
    """Celda horaria de base: temporada, mes, tipo de día, hora."""
    season: str
    month: int
    dt: str
    hour: int
    weight: float  # duración relativa dentro de su bloque original

    @property
    def block(self) -> str:
        return self.season + ("D" if 6 <= self.hour < 22 else "N")


def _slots(daytypes: str) -> list[Slot]:
    return [
        Slot(MONTH_SEASON[m], m, dt, h, share)
        for m in range(1, 13) for dt, share in DAYTYPES[daytypes] for h in range(24)
    ]


def _ts_name(level: Level, s: Slot) -> str | None:
    for h0, h1 in PARTITIONS[level.blocks]:
        if h0 <= s.hour < h1 or h0 <= s.hour + 24 < h1:
            period = f"{s.month:02d}" if level.months else "00"
            return f"{s.season}{period}{s.dt}{h0 % 24:02d}"
    raise AssertionError(s)


def disaggregate(base: Case, level: Level) -> Case:
    years = base.sets["YEAR"]
    slots = _slots(level.daytypes)
    ts_of = {s: _ts_name(level, s) for s in slots}
    ts_list = list(dict.fromkeys(ts_of.values()))
    block_of = {ts_of[s]: s.block for s in slots}
    for s in slots:
        assert block_of[ts_of[s]] == s.block, "un timeslice cruza un bloque original"

    dur = {}  # duración relativa de cada slot (para repartir YearSplit del bloque)
    for s in slots:
        dur[s] = s.weight
    block_dur = {}
    for s in slots:
        block_dur[s.block] = block_dur.get(s.block, 0.0) + dur[s]

    ys0 = base.params["YearSplit"]
    params: dict[str, Param] = {}
    for name, p in base.params.items():
        params[name] = Param(name, p.dims, p.default, {} if "TIMESLICE" in p.dims else dict(p.values))

    # YearSplit: el del bloque, repartido por duración.
    ys_slot = {}
    for y in years:
        for s in slots:
            ys_slot[(s, y)] = ys0.get((s.block, y)) * dur[s] / block_dur[s.block]
            key = (ts_of[s], y)
            params["YearSplit"].values[key] = params["YearSplit"].values.get(key, 0.0) + ys_slot[(s, y)]

    # SpecifiedDemandProfile: energía del bloque repartida por forma × duración.
    sdp0 = base.params["SpecifiedDemandProfile"]
    fuels = sorted({k[1] for k in sdp0.values})
    region = base.sets["REGION"][0]
    for f in fuels:
        w = {s: demand_shape(f, s.hour, s.month, s.dt) * dur[s] for s in slots}
        wb = {}
        for s in slots:
            wb[s.block] = wb.get(s.block, 0.0) + w[s]
        for y in years:
            for s in slots:
                v = sdp0.get((region, f, s.block, y)) * w[s] / wb[s.block]
                key = (region, f, ts_of[s], y)
                params["SpecifiedDemandProfile"].values[key] = params["SpecifiedDemandProfile"].values.get(key, 0.0) + v

    # CapacityFactor: forma escalada para que el promedio ponderado del bloque
    # sea el original, con tope 1 (redistribuyendo lo recortado).
    cf0 = base.params["CapacityFactor"]
    techs = sorted({k[1] for k in cf0.values})
    cf = params["CapacityFactor"]
    for t in techs:
        for y in years:
            slot_cf = {}
            for block in block_dur:
                members = [s for s in slots if s.block == block]
                target = cf0.get((region, t, block, y))
                slot_cf.update(_calibrate(members, {s: cf_shape(t, s.hour, s.month, s.dt) for s in members},
                                          {s: dur[s] for s in members}, target))
            num, den = {}, {}
            for s in slots:
                k = ts_of[s]
                num[k] = num.get(k, 0.0) + slot_cf[s] * dur[s]
                den[k] = den.get(k, 0.0) + dur[s]
            for k in ts_list:
                cf.values[(region, t, k, y)] = num[k] / den[k]

    sets = {k: list(v) for k, v in base.sets.items()}
    sets["TIMESLICE"] = ts_list
    params["Conversionls"].values = {(t, "1"): 1.0 for t in ts_list}
    params["Conversionld"].values = {(t, "1"): 1.0 for t in ts_list}
    params["Conversionlh"].values = {(t, "1"): 1.0 for t in ts_list}
    sets["SEASON"], sets["DAYTYPE"], sets["DAILYTIMEBRACKET"] = ["1"], ["1"], ["1"]
    return Case(sets, params)


def _calibrate(members, shape, dur, target):
    if target == 0:
        return {s: 0.0 for s in members}
    fixed: dict = {}
    free = list(members)
    for _ in range(50):
        remaining = target * sum(dur[s] for s in members) - sum(fixed[s] * dur[s] for s in fixed)
        base = sum(shape[s] * dur[s] for s in free)
        if base <= 0:
            raise ValueError("forma nula con objetivo positivo")
        k = remaining / base
        over = [s for s in free if shape[s] * k > 1.0]
        if not over:
            out = {s: shape[s] * k for s in free}
            out.update(fixed)
            return out
        for s in over:
            fixed[s] = 1.0
            free.remove(s)
    raise RuntimeError("calibración de CapacityFactor no converge")


def check_calibration(base: Case, fine: Case, level: Level) -> float:
    """Máximo error al re-agregar los perfiles finos a los 6 bloques originales."""
    region = base.sets["REGION"][0]
    y = base.sets["YEAR"][0]
    block = {ts: ts[0] + ("D" if 6 <= int(ts[-2:]) < 22 else "N") for ts in fine.sets["TIMESLICE"]}
    err = 0.0
    ys = fine.params["YearSplit"]
    for b in base.sets["TIMESLICE"]:
        mem = [ts for ts in fine.sets["TIMESLICE"] if block[ts] == b]
        err = max(err, abs(sum(ys.get((ts, y)) for ts in mem) - base.params["YearSplit"].get((b, y))))
        for (r, t, _, yy), v0 in base.params["CapacityFactor"].values.items():
            if yy != y or _ != b:
                continue
            avg = sum(fine.params["CapacityFactor"].get((r, t, ts, y)) * ys.get((ts, y)) for ts in mem) \
                / sum(ys.get((ts, y)) for ts in mem)
            err = max(err, abs(avg - v0))
        for (r, f, _, yy), v0 in base.params["SpecifiedDemandProfile"].values.items():
            if yy != y or _ != b:
                continue
            tot = sum(fine.params["SpecifiedDemandProfile"].get((r, f, ts, y)) for ts in mem)
            err = max(err, abs(tot - v0))
    return err


# ---------------------------------------------------------------------------
# Ejecución con tiempo y memoria
# ---------------------------------------------------------------------------

def _rss_gb(pid: int) -> float:
    out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return int(out) / 2**20 if out else 0.0


def _run(cmd: list[str], timeout: float, mem_limit_gb: float, cwd: Path | None = None) -> dict:
    """Corre un comando midiendo tiempo de reloj y RSS máximo; lo mata si se pasa."""
    t0 = time.perf_counter()
    with tempfile.TemporaryFile("w+") as log:
        proc = subprocess.Popen(cmd, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, text=True)
        peak, status = 0.0, "ok"
        while proc.poll() is None:
            peak = max(peak, _rss_gb(proc.pid))
            if time.perf_counter() - t0 > timeout:
                status = "timeout"
            elif peak > mem_limit_gb:
                status = "memory"
            if status != "ok":
                proc.kill()
                proc.wait()
                break
            time.sleep(0.5)
        log.seek(0)
        output = log.read()
    if status == "ok" and proc.returncode != 0:
        status = f"error({proc.returncode})"
    return {"status": status, "seconds": time.perf_counter() - t0, "peak_gb": peak,
            "output": output[-4000:]}


UPME_SNIPPET = r"""
import json, sys, time
sys.path.insert(0, ".")
from app.simulation.osemosys_core import run_osemosys_from_excel
t = time.perf_counter()
res = run_osemosys_from_excel(sys.argv[1], solver_name="highs")
print("@@RESULT@@" + json.dumps({
    "objective": res.get("objective_value"),
    "solver_status": res.get("solver_status"),
    "timings": res.get("model_timings", {}),
    "total_seconds": time.perf_counter() - t,
}, default=str))
"""

REF_SNIPPET = r"""
import json, sys, time, highspy
h = highspy.Highs(); h.setOptionValue("output_flag", False)
t = time.perf_counter(); h.readModel(sys.argv[1]); t_read = time.perf_counter() - t
t = time.perf_counter(); h.run(); t_solve = time.perf_counter() - t
print("@@RESULT@@" + json.dumps({
    "objective": h.getInfo().objective_function_value,
    "solver_status": h.modelStatusToString(h.getModelStatus()),
    "rows": h.getNumRow(), "cols": h.getNumCol(),
    "read_seconds": t_read, "solve_seconds": t_solve,
}))
"""


def _parse(run: dict) -> dict:
    for line in run["output"].splitlines():
        if line.startswith("@@RESULT@@"):
            run.update(json.loads(line[len("@@RESULT@@"):]))
    run.pop("output", None) if "objective" in run else None
    return run


def run_level(level: Level, base: Case, *, timeout: float, mem_gb: float, reference: bool,
              keep: bool) -> dict:
    py = sys.executable
    work = LADDER_DIR / level.name
    work.mkdir(parents=True, exist_ok=True)

    t = time.perf_counter()
    fine = disaggregate(base, level)
    calib_err = check_calibration(base, fine, level)
    xlsx = work / f"ATLANTIS_{level.name}_SAND.xlsx"
    build_sand(fine).to_excel(xlsx, sheet_name="Parameters", index=False)
    dat = write_dat(fine, work / f"atlantis_{level.name}.dat")
    result = {
        "level": level.name, "n_ts": level.n_ts, "months": level.months,
        "daytypes": level.daytypes, "blocks_per_day": level.blocks,
        "calibration_max_error": calib_err, "build_inputs_seconds": time.perf_counter() - t,
    }
    print(f"[{level.name}] {level.n_ts} TS — entradas listas (error calibración {calib_err:.2e})", flush=True)

    upme = _run([py, "-c", UPME_SNIPPET, str(xlsx)], timeout, mem_gb, cwd=REPO_ROOT / "backend")
    result["upme"] = _parse(upme)
    print(f"[{level.name}] UPME: {upme['status']} {upme.get('objective')} "
          f"{upme['seconds']:.1f}s pico {upme['peak_gb']:.2f} GB", flush=True)

    if reference:
        mps = work / f"atlantis_{level.name}.mps"
        free_gb = shutil.disk_usage(work).free / 2**30
        est_gb = level.n_ts * 0.011
        if est_gb > free_gb - 1.5:
            result["reference"] = {"status": f"omitida: MPS ~{est_gb:.1f} GB, libres {free_gb:.1f} GB"}
        else:
            tr = _run(["glpsol", "-m", str(SOURCE_MODEL), "-d", str(dat), "--check", "--wfreemps", str(mps)],
                      timeout, mem_gb)
            tr.pop("output", None) if tr["status"] == "ok" else None
            ref = {"glpsol": tr}
            if tr["status"] == "ok":
                ref["highs"] = _parse(_run([py, "-c", REF_SNIPPET, str(mps)], timeout, mem_gb))
            result["reference"] = ref
            if not keep and mps.exists():
                mps.unlink()
        r = result["reference"]
        print(f"[{level.name}] referencia: {json.dumps({k: (v.get('status'), v.get('objective'), round(v.get('seconds', 0), 1)) if isinstance(v, dict) else v for k, v in r.items()})}", flush=True)

    if not keep:
        for f in (xlsx, dat):
            f.unlink(missing_ok=True)
    return result


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--levels", nargs="+", default=["L006"], help="Nombres de nivel o 'all'")
    parser.add_argument("--timeout", type=float, default=1800, help="Segundos por corrida")
    parser.add_argument("--mem-gb", type=float, default=5.0, help="RSS máximo por corrida")
    parser.add_argument("--no-reference", action="store_true")
    parser.add_argument("--keep", action="store_true", help="Conservar xlsx/dat/mps")
    args = parser.parse_args()

    names = [lv.name for lv in LEVELS] if args.levels == ["all"] else args.levels
    base = make_variant(read_case(SOURCE_DATA, SOURCE_MODEL), 6, storage=False, re_target=False)
    results = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    for name in names:
        res = run_level(LEVELS_BY_NAME[name], base, timeout=args.timeout, mem_gb=args.mem_gb,
                        reference=not args.no_reference, keep=args.keep)
        results[name] = res
        RESULTS.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
        if res["upme"]["status"] != "ok":
            print(f"[{name}] UPME no terminó ({res['upme']['status']}); se detiene la escalera.")
            break


if __name__ == "__main__":
    _main()
