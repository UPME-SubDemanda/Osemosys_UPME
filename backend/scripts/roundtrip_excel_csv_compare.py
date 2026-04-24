#!/usr/bin/env python3
"""Compara escenario desde Excel vs escenario creado desde los CSV generados por el pipeline local.

Flujo (alineado con run_local.py / run_osemosys_from_db):
  1) Crear escenario vacío e importar el Excel (OfficialImportService.import_xlsm).
  2) Ejecutar run_data_processing (export + pasos notebook) → directorio de CSVs temporales.
  3) Importar ese directorio con CsvScenarioImportService.import_from_directory → segundo escenario.
  4) Comparar CSV ejecutando run_data_processing otra vez sobre cada escenario (el Excel necesita
     el pipeline; el importado PREPROCESSED_CSV solo re-exporta). Así se compara lo que ve el solver,
     no la OPV cruda del Excel frente a la OPV ya procesada del CSV.

Uso:
  cd backend
  DATABASE_URL=postgresql+psycopg://... python3 scripts/roundtrip_excel_csv_compare.py \\
    --excel /ruta/SAND_integrado_PA_MR_20_04.xlsx

Por defecto usa la misma DATABASE_URL que run_local.py (localhost:55432) si no está definida.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import func, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://osemosys:osemosys@localhost:55432/osemosys",
)

from app.db.session import SessionLocal  # noqa: E402
from app.models import OsemosysParamValue, User  # noqa: E402
from app.services.csv_scenario_import_service import CsvScenarioImportService  # noqa: E402
from app.services.official_import_service import OfficialImportService  # noqa: E402
from app.services.scenario_service import ScenarioService  # noqa: E402
from app.simulation.core.data_processing import run_data_processing  # noqa: E402


def _norm_param(name: str) -> str:
    return "".join(ch for ch in (name or "").strip().lower() if ch.isalnum())


def _param_key(row: OsemosysParamValue) -> tuple:
    return (
        _norm_param(row.param_name),
        row.id_region,
        row.id_technology,
        row.id_fuel,
        row.id_emission,
        row.id_timeslice,
        row.id_mode_of_operation,
        row.id_season,
        row.id_daytype,
        row.id_dailytimebracket,
        row.id_storage_set,
        row.id_udc_set,
        row.year,
    )


def _load_opv_map(db, scenario_id: int) -> dict[tuple, float]:
    rows = (
        db.execute(select(OsemosysParamValue).where(OsemosysParamValue.id_scenario == scenario_id))
        .scalars()
        .all()
    )
    return {_param_key(r): float(r.value) for r in rows}


def _compare_opv_maps(
    m1: dict[tuple, float],
    m2: dict[tuple, float],
    *,
    tol: float,
) -> tuple[int, int, int, list[tuple]]:
    common = m1.keys() & m2.keys()
    only1 = m1.keys() - m2.keys()
    only2 = m2.keys() - m1.keys()
    mismatches: list[tuple] = []
    for k in common:
        if abs(m1[k] - m2[k]) > tol:
            mismatches.append((k, m1[k], m2[k]))
    return len(only1), len(only2), len(mismatches), mismatches


def _sorted_csv_df(path: Path) -> pd.DataFrame | None:
    if not path.is_file():
        return None
    df = pd.read_csv(path, dtype=str)
    df = df.fillna("")
    cols = sorted(df.columns)
    df = df[cols]
    return df.sort_values(cols).reset_index(drop=True)


def _compare_csv_dirs(d1: Path, d2: Path) -> tuple[list[str], list[str], list[str]]:
    """Devuelve (solo_en_d1, solo_en_d2, archivos_con_diferencias)."""
    names1 = {p.name for p in d1.glob("*.csv")}
    names2 = {p.name for p in d2.glob("*.csv")}
    only1 = sorted(names1 - names2)
    only2 = sorted(names2 - names1)
    diff_files: list[str] = []
    for name in sorted(names1 & names2):
        a = _sorted_csv_df(d1 / name)
        b = _sorted_csv_df(d2 / name)
        if a is None or b is None:
            diff_files.append(name)
            continue
        if not a.equals(b):
            diff_files.append(name)
    return only1, only2, diff_files


def run_excel_csv_roundtrip(
    excel_path: Path,
    *,
    sheet: str = "Parameters",
    seed_user: str = "seed",
    preserve_timeslices: bool = False,
    tol: float = 1e-6,
    keep_temp: bool = False,
    pipeline_csv_dir: Path | None = None,
    run_id: str | None = None,
) -> int:
    """Excel → import oficial → ``run_data_processing`` → import CSV → comparar CSV finales.

    La comparación final vuelve a ejecutar ``run_data_processing`` por escenario: el importado
    ``PREPROCESSED_CSV`` solo re-exporta; el del Excel aplica el pipeline completo. Eso alinea
    la prueba con lo que hace ``run_osemosys_from_db`` antes del solve.

    Returns
    -------
    int
        0 éxito (CSV post-pipeline idénticos u OPV equivalente según criterio), 1 divergencia CSV,
        2 archivo Excel inexistente, 3 usuario seed inexistente.
    """
    excel_path = excel_path.resolve()
    if not excel_path.is_file():
        print(f"ERROR: No existe el archivo: {excel_path}", file=sys.stderr)
        return 2

    content = excel_path.read_bytes()
    base_name = excel_path.stem[:40]
    rid = run_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if pipeline_csv_dir is not None:
        tmp_pipeline = pipeline_csv_dir.resolve()
        tmp_pipeline.mkdir(parents=True, exist_ok=True)
    else:
        tmp_pipeline = PROJECT_ROOT / "tmp" / f"roundtrip_pipeline_{rid}"
        tmp_pipeline.mkdir(parents=True, exist_ok=True)

    tmp_reexport_s1 = PROJECT_ROOT / "tmp" / f"roundtrip_export_s1_{rid}"
    tmp_reexport_s2 = PROJECT_ROOT / "tmp" / f"roundtrip_export_s2_{rid}"
    for p in (tmp_reexport_s1, tmp_reexport_s2):
        p.mkdir(parents=True, exist_ok=True)

    print(f"DATABASE_URL: {os.environ.get('DATABASE_URL', '')[:50]}...")
    print(f"Excel: {excel_path}")
    print(f"CSV pipeline dir: {tmp_pipeline}")
    print()

    with SessionLocal() as db:
        user = db.execute(select(User).where(User.username == seed_user)).scalar_one_or_none()
        if user is None:
            print(f"ERROR: Usuario '{seed_user}' no existe en la BD.", file=sys.stderr)
            print("Crea el usuario seed o pasa seed_user.", file=sys.stderr)
            return 3

        name_excel = f"RT_EXCEL_{base_name}_{rid}"
        created = ScenarioService.create(
            db,
            current_user=user,
            name=name_excel,
            description="Roundtrip test: import Excel",
            edit_policy="OWNER_ONLY",
            is_template=False,
            simulation_type="NATIONAL",
            skip_populate_defaults=True,
        )
        sid_excel = int(created["id"])
        print(f"Escenario Excel: id={sid_excel} name={name_excel!r}")

        OfficialImportService.import_xlsm(
            db,
            filename=excel_path.name,
            content=content,
            imported_by=user.username,
            selected_sheet_name=sheet,
            scenario_id_override=sid_excel,
            use_default_scenario=False,
            collapse_timeslices=not preserve_timeslices,
        )
        db.commit()

        n_rows_excel = int(
            db.scalar(
                select(func.count())
                .select_from(OsemosysParamValue)
                .where(OsemosysParamValue.id_scenario == sid_excel)
            )
            or 0
        )
        print(f"  Filas osemosys_param_value tras Excel: {n_rows_excel}")

        print("Ejecutando run_data_processing (mismo pipeline que run_osemosys_from_db)...")
        run_data_processing(db, scenario_id=sid_excel, csv_dir=str(tmp_pipeline))
        db.commit()

        name_csv = f"RT_CSV_{base_name}_{rid}"
        created_csv = CsvScenarioImportService.import_from_directory(
            db,
            current_user=user,
            csv_root=tmp_pipeline,
            scenario_name=name_csv,
            description="Roundtrip test: import CSV desde pipeline",
            edit_policy="OWNER_ONLY",
            simulation_type="NATIONAL",
            tag_ids=[],
        )
        sid_csv = int(created_csv["id"])
        print(f"Escenario CSV: id={sid_csv} name={name_csv!r}")

        n_rows_csv = int(
            db.scalar(
                select(func.count())
                .select_from(OsemosysParamValue)
                .where(OsemosysParamValue.id_scenario == sid_csv)
            )
            or 0
        )
        print(f"  Filas osemosys_param_value tras import CSV: {n_rows_csv}")

        m_excel = _load_opv_map(db, sid_excel)
        m_csv = _load_opv_map(db, sid_csv)
        o1, o2, nm, mism = _compare_opv_maps(m_excel, m_csv, tol=tol)
        print()
        print("=== Comparación directa osemosys_param_value (Excel vs CSV import) ===")
        print(f"  Claves solo en escenario Excel: {o1}")
        print(f"  Claves solo en escenario CSV:    {o2}")
        print(f"  Claves comunes con valor distinto: {nm}")
        if mism[:5]:
            print("  Primeras diferencias (clave, val_excel, val_csv):")
            for item in mism[:5]:
                print(f"    {item}")
        if len(mism) > 5:
            print(f"    ... y {len(mism) - 5} más")

        print()
        print(
            "=== Comparación de CSV post-pipeline (run_data_processing × escenario; paridad solver) ==="
        )
        run_data_processing(db, scenario_id=sid_excel, csv_dir=str(tmp_reexport_s1))
        run_data_processing(db, scenario_id=sid_csv, csv_dir=str(tmp_reexport_s2))
        db.commit()

        only1, only2, diff_files = _compare_csv_dirs(tmp_reexport_s1, tmp_reexport_s2)
        print(f"  CSV solo en export Excel: {len(only1)} archivos")
        if only1[:10]:
            print(f"    {only1[:10]}")
        print(f"  CSV solo en export CSV:   {len(only2)} archivos")
        if only2[:10]:
            print(f"    {only2[:10]}")
        print(f"  CSV con contenido distinto: {len(diff_files)}")
        if diff_files[:15]:
            print(f"    {diff_files[:15]}")
        if len(diff_files) > 15:
            print(f"    ... y {len(diff_files) - 15} más")

    if not keep_temp:
        shutil.rmtree(tmp_reexport_s1, ignore_errors=True)
        shutil.rmtree(tmp_reexport_s2, ignore_errors=True)
        if pipeline_csv_dir is None:
            shutil.rmtree(tmp_pipeline, ignore_errors=True)
    else:
        print()
        print("Directorios conservados (keep_temp):")
        print(f"  pipeline: {tmp_pipeline}")
        print(f"  reexport excel scenario: {tmp_reexport_s1}")
        print(f"  reexport csv scenario:   {tmp_reexport_s2}")

    reexport_ok = len(only1) == 0 and len(only2) == 0 and len(diff_files) == 0
    opv_identical = o1 == 0 and o2 == 0 and nm == 0
    print()
    if reexport_ok and opv_identical:
        print("RESULTADO: OPV idénticos y re-export CSV idénticos (round-trip completo).")
        return 0
    if reexport_ok:
        print(
            "RESULTADO: Re-export CSV idéntico (mismo modelo para el solver). "
            "Las filas en BD pueden diferir (Excel disperso vs CSV denso tras el pipeline).",
        )
        return 0
    print(
        "RESULTADO: Diferencias en re-export CSV — revisa archivos listados arriba. "
        "OPV: puede haber divergencia esperada entre import Excel y import CSV.",
    )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Excel → CSV pipeline → import CSV → comparar exportaciones")
    parser.add_argument(
        "--excel",
        type=Path,
        required=True,
        help="Ruta al .xlsx / .xlsm SAND",
    )
    parser.add_argument(
        "--sheet",
        type=str,
        default="Parameters",
        help="Nombre de la hoja (default Parameters)",
    )
    parser.add_argument(
        "--seed-user",
        type=str,
        default="seed",
        help="Usuario existente para crear escenarios (default seed)",
    )
    parser.add_argument(
        "--preserve-timeslices",
        action="store_true",
        help="Importar Excel sin colapsar timeslices (default: colapsar, alineado con export)",
    )
    parser.add_argument(
        "--tol",
        type=float,
        default=1e-6,
        help="Tolerancia para comparar valores numéricos en osemosys_param_value",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="No borrar directorios temporales (imprime rutas)",
    )
    parser.add_argument(
        "--pipeline-csv-dir",
        type=Path,
        default=None,
        help="Escribe los CSV del pipeline aquí; el directorio no se elimina al terminar (solo aplica limpieza a carpetas temporales de re-export si no usas --keep-temp).",
    )
    args = parser.parse_args()
    return run_excel_csv_roundtrip(
        args.excel,
        sheet=args.sheet,
        seed_user=args.seed_user,
        preserve_timeslices=args.preserve_timeslices,
        tol=args.tol,
        keep_temp=args.keep_temp,
        pipeline_csv_dir=args.pipeline_csv_dir,
    )


if __name__ == "__main__":
    raise SystemExit(main())
