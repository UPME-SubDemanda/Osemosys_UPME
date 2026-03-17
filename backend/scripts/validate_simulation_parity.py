"""Validación numérica de simulaciones contra benchmarks registrados en BD."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import and_, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import SessionLocal
from app.models import Scenario, SimulationBenchmark, SimulationJob
from app.simulation.benchmark import compare_with_tolerance


def main() -> None:
    """Ejecuta comparación de corridas exitosas vs benchmarks almacenados."""
    tolerance = 1e-4
    with SessionLocal() as session:
        benchmarks = session.execute(select(SimulationBenchmark)).scalars().all()
        if not benchmarks:
            print("No hay benchmarks registrados.")
            return

        has_failures = False
        for bench in benchmarks:
            scenario = session.execute(
                select(Scenario).where(Scenario.name == bench.scenario_name, Scenario.is_template.is_(False))
            ).scalar_one_or_none()
            if not scenario:
                print(f"[WARN] Benchmark sin escenario: {bench.scenario_name}")
                has_failures = True
                continue

            latest_job = session.execute(
                select(SimulationJob)
                .where(
                    and_(
                        SimulationJob.scenario_id == scenario.id,
                        SimulationJob.status == "SUCCEEDED",
                    )
                )
                .order_by(SimulationJob.finished_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if not latest_job or not latest_job.result_ref:
                print(f"[WARN] Sin corrida exitosa para escenario {scenario.name}")
                has_failures = True
                continue

            result_path = PROJECT_ROOT / latest_job.result_ref
            if not result_path.exists():
                # fallback para worker, donde los artefactos viven dentro del contenedor.
                print(f"[WARN] Artefacto no encontrado localmente: {result_path}")
                has_failures = True
                continue

            result_data = json.loads(result_path.read_text(encoding="utf-8"))
            ref_metrics = json.loads(bench.metrics_json or "{}")
            actual_metrics = {
                "objective_value": float(result_data.get("objective_value", 0.0)),
                "coverage_ratio": float(result_data.get("coverage_ratio", 0.0)),
                "total_demand": float(result_data.get("total_demand", 0.0)),
                "total_unmet": float(result_data.get("total_unmet", 0.0)),
            }
            is_ok, errors = compare_with_tolerance(
                reference=ref_metrics,
                actual=actual_metrics,
                tolerance=tolerance,
            )
            status = "OK" if is_ok else "FAIL"
            print(f"[{status}] {bench.benchmark_key} escenario={scenario.name} errors={errors}")
            if not is_ok:
                has_failures = True

        if has_failures:
            raise SystemExit(1)
    print("Validación numérica finalizada sin fallos.")


if __name__ == "__main__":
    main()


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Validar regresión numérica del motor OSeMOSYS frente a referencias.
#
# Posibles mejoras:
# - Emitir reporte estructurado (JSON/JUnit) para CI.
#
# Riesgos en producción:
# - Depende de artefactos locales; en contenedores puede requerir volumen compartido.
#
# Escalabilidad:
# - I/O-bound al leer BD/artefactos y CPU-bound bajo en comparación.
