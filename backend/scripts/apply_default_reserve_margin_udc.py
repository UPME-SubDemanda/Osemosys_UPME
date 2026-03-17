from __future__ import annotations

from pathlib import Path
import sys

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import SessionLocal  # noqa: E402
from app.models import Scenario  # noqa: E402
from app.services.scenario_service import ScenarioService  # noqa: E402


def main() -> None:
    """Aplica UDC RESERVEMARGIN por defecto a todos los escenarios existentes."""
    with SessionLocal() as session:
        scenarios = session.execute(select(Scenario)).scalars().all()
        for sc in scenarios:
            ScenarioService.ensure_default_reserve_margin_udc(session, scenario_id=int(sc.id))
        print(f"UDC RESERVEMARGIN aplicados/actualizados en {len(scenarios)} escenarios.")


if __name__ == "__main__":
    main()

