"""Utilidades CLI para inspección local de base SQLite/PostgreSQL."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from sqlalchemy import inspect, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import engine


def _all_tables() -> list[str]:
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    for schema_name in ("core", "osemosys"):
        try:
            for t in insp.get_table_names(schema=schema_name):
                tables.add(f"{schema_name}.{t}")
        except Exception:
            continue
    return sorted(tables)


def _write_rows_to_csv(path: Path, headers: list[str], rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def _safe_sql(sql: str) -> bool:
    normalized = (sql or "").strip().lower()
    return normalized.startswith("select") or normalized.startswith("with") or normalized.startswith("pragma")


def cmd_list_tables(with_counts: bool) -> int:
    tables = _all_tables()
    print("Tablas disponibles:")
    with engine.connect() as conn:
        for table in tables:
            if with_counts:
                quoted = '"' + table.replace('"', '""') + '"'
                try:
                    count = conn.execute(text(f"SELECT COUNT(*) FROM {quoted}")).scalar_one()
                    print(f"- {table} ({count} filas)")
                except Exception:
                    print(f"- {table} (conteo no disponible)")
            else:
                print(f"- {table}")
    return 0


def cmd_dump_table(table_name: str, output_file: Path | None, limit: int | None) -> int:
    table = table_name.strip()
    if not table:
        print("[ERROR] table_name es requerido.")
        return 1

    output = output_file or (PROJECT_ROOT / "tmp" / "local" / "tables" / f"{table.replace('.', '_')}.csv")
    quoted = '"' + table.replace('"', '""') + '"'
    sql = f"SELECT * FROM {quoted}"
    if limit and limit > 0:
        sql += f" LIMIT {int(limit)}"

    with engine.connect() as conn:
        result = conn.execute(text(sql))
        headers = list(result.keys())
        rows = list(result.fetchall())
    _write_rows_to_csv(output, headers, rows)
    print(f"Tabla exportada: {output}")
    print(f"Filas exportadas: {len(rows)}")
    return 0


def cmd_dump_all_tables(output_dir: Path | None, limit: int | None) -> int:
    tables = _all_tables()
    base_dir = output_dir or (PROJECT_ROOT / "tmp" / "local" / "tables")
    base_dir.mkdir(parents=True, exist_ok=True)
    total_files = 0
    for table in tables:
        out = base_dir / f"{table.replace('.', '_')}.csv"
        rc = cmd_dump_table(table_name=table, output_file=out, limit=limit)
        if rc != 0:
            return rc
        total_files += 1
    print(f"Exportación completa: {total_files} tablas en {base_dir}")
    return 0


def cmd_query(sql: str, output_file: Path | None, limit: int | None) -> int:
    if not _safe_sql(sql):
        print("[ERROR] Solo se permiten consultas de lectura (SELECT/WITH/PRAGMA).")
        return 1

    final_sql = sql.strip().rstrip(";")
    if limit and limit > 0:
        final_sql = f"SELECT * FROM ({final_sql}) q LIMIT {int(limit)}"

    with engine.connect() as conn:
        result = conn.execute(text(final_sql))
        headers = list(result.keys())
        rows = list(result.fetchall())

    print("Columnas:", ", ".join(headers))
    print(f"Filas: {len(rows)}")
    for row in rows[:10]:
        print(row)

    if output_file:
        _write_rows_to_csv(output_file, headers, rows)
        print(f"Resultado exportado: {output_file}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspección local de base de datos")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list-tables", help="Listar tablas disponibles")
    p_list.add_argument("--with-counts", action="store_true", help="Incluye conteo de filas por tabla")

    p_dump = sub.add_parser("dump-table", help="Exportar una tabla a CSV")
    p_dump.add_argument("--table-name", required=True, help="Nombre de la tabla (ej: simulation_job)")
    p_dump.add_argument("--output-file", type=Path, help="Ruta CSV de salida")
    p_dump.add_argument("--limit", type=int, help="Limitar filas exportadas")

    p_dump_all = sub.add_parser("dump-all-tables", help="Exportar todas las tablas a CSV")
    p_dump_all.add_argument("--output-dir", type=Path, help="Directorio de salida para CSVs")
    p_dump_all.add_argument("--limit", type=int, help="Limitar filas por tabla")

    p_query = sub.add_parser("query", help="Ejecutar consulta SQL de solo lectura")
    p_query.add_argument("--sql", required=True, help="Consulta SQL (SELECT/WITH/PRAGMA)")
    p_query.add_argument("--output-file", type=Path, help="Ruta CSV de salida")
    p_query.add_argument("--limit", type=int, help="Limitar filas de salida")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "list-tables":
        return cmd_list_tables(with_counts=bool(args.with_counts))
    if args.command == "dump-table":
        return cmd_dump_table(
            table_name=args.table_name,
            output_file=args.output_file,
            limit=args.limit,
        )
    if args.command == "query":
        return cmd_query(
            sql=args.sql,
            output_file=args.output_file,
            limit=args.limit,
        )
    if args.command == "dump-all-tables":
        return cmd_dump_all_tables(output_dir=args.output_dir, limit=args.limit)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

