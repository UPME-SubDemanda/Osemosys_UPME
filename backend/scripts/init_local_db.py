"""Inicializa BD local para modo sin Docker.

Para SQLite crea el esquema con SQLAlchemy `create_all`.
Para PostgreSQL ejecuta `alembic upgrade head`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine

# Importa modelos para registrar metadata antes de create_all.
import app.models  # noqa: F401


def _ensure_sqlite_parent(url: str) -> None:
    parsed = make_url(url)
    db_path = parsed.database
    if not db_path or db_path == ":memory:":
        return
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)


def main() -> None:
    settings = get_settings()
    if settings.is_sqlite():
        _ensure_sqlite_parent(settings.database_url)
        Base.metadata.create_all(bind=engine)
        print("Base SQLite inicializada con create_all.")
        return

    result = subprocess.run(["alembic", "upgrade", "head"], cwd=str(PROJECT_ROOT), check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    print("Migraciones Alembic aplicadas.")


if __name__ == "__main__":
    main()

