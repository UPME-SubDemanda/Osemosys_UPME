"""Siembra labels en ``catalog_meta_label`` para TODOS los códigos usados en
resultados (``osemosys_output_param_value``) que aún no tienen label.

Para cada código faltante genera un label con la heurística ``_dynamic_label``
de ``app.visualization.labels``. El admin luego puede editarlos manualmente
desde la UI.

Cubre: technology_name, fuel_name, emission_name.

Uso dentro del contenedor api:

    docker compose exec api python scripts/seed_missing_result_labels.py
    docker compose exec api python scripts/seed_missing_result_labels.py --dry-run

Idempotente: sólo inserta códigos que no existen en ``catalog_meta_label``.
"""

from __future__ import annotations

import argparse
import logging

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import CatalogMetaLabel, OsemosysOutputParamValue
from app.visualization.catalog_reader import bump_version
from app.visualization.labels import _dynamic_label

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("seed-missing")

_SOURCES = (
    ("technology_name", "technology"),
    ("fuel_name", "fuel"),
    ("emission_name", "emission"),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with SessionLocal() as db:
        # Códigos ya presentes (también filtrados por prefijo FUEL:: para
        # evitar colisión con las etiquetas de fuel del seed inicial).
        existing = {
            r[0]
            for r in db.execute(select(CatalogMetaLabel.code)).all()
        }
        logger.info("Labels existentes en BD: %d", len(existing))

        # Códigos usados en resultados.
        missing_by_category: dict[str, set[str]] = {}
        for col, category in _SOURCES:
            rows = db.execute(
                select(getattr(OsemosysOutputParamValue, col))
                .where(getattr(OsemosysOutputParamValue, col).is_not(None))
                .distinct()
            ).all()
            codes = {r[0] for r in rows if r[0]}
            missing = {c for c in codes if c not in existing}
            missing_by_category[category] = missing
            logger.info(
                "[%s] total distintos=%d, ya con label=%d, a agregar=%d",
                col,
                len(codes),
                len(codes & existing),
                len(missing),
            )

        # Generar y (opcional) escribir.
        total_added = 0
        for category, codes in missing_by_category.items():
            if not codes:
                continue
            for code in sorted(codes):
                label = _dynamic_label(code)
                # Si la heurística devolvió el mismo código, igual lo sembramos
                # para que el admin lo vea como "pendiente de revisión".
                if args.dry_run:
                    logger.info("  DRY %-40s | %s | %s", code, category, label)
                    continue
                db.add(
                    CatalogMetaLabel(
                        code=code,
                        label_es=label,
                        category=category,
                    )
                )
                total_added += 1

        if args.dry_run:
            logger.info(
                "DRY-RUN terminado. Total a agregar: %d",
                sum(len(s) for s in missing_by_category.values()),
            )
            return

        if total_added == 0:
            logger.info("Nada que agregar — BD al día.")
            return

        db.commit()
        bump_version()
        logger.info("✅ Seeded %d labels desde heurística _dynamic_label.", total_added)


if __name__ == "__main__":
    main()
