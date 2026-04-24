"""Servicios para administración del catálogo editable de visualización."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models import (
    CatalogMetaAudit,
    CatalogMetaChartConfig,
    CatalogMetaChartModule,
    CatalogMetaChartSubfilter,
    CatalogMetaChartSubmodule,
    CatalogMetaColorPalette,
    CatalogMetaLabel,
    CatalogMetaSectorMapping,
    CatalogMetaTechFamily,
    CatalogMetaVariableUnit,
    User,
)
from app.models.core.user import User as CoreUser
from app.visualization.catalog_reader import bump_version


def _write_audit(
    db: Session,
    *,
    table_name: str,
    row_id: int | None,
    action: str,  # "INSERT" | "UPDATE" | "DELETE"
    diff: dict[str, Any] | None,
    changed_by: UUID | None,
) -> None:
    """Añade una entrada al log ``catalog_meta_audit``.

    La sesión NO se commitea — debe ser parte de la misma transacción del
    write principal, de modo que ambos se rollbackean si algo falla.
    """
    db.add(
        CatalogMetaAudit(
            table_name=table_name,
            row_id=row_id,
            action=action,
            diff_json=diff,
            changed_by=changed_by,
        )
    )


def _snapshot(row: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    """Extrae un dict {field: value} — acepta tipos primitivos y None."""
    out: dict[str, Any] = {}
    for f in fields:
        v = getattr(row, f, None)
        if isinstance(v, UUID):
            v = str(v)
        out[f] = v
    return out


_COLOR_FIELDS = ("key", "group", "color_hex", "description", "sort_order")
_LABEL_FIELDS = ("code", "label_es", "label_en", "category", "sort_order")


class CatalogMetaColorService:
    """CRUD de ``catalog_meta_color_palette`` con auditoría."""

    @staticmethod
    def list(
        db: Session,
        *,
        group: str | None = None,
    ) -> list[CatalogMetaColorPalette]:
        stmt = select(CatalogMetaColorPalette)
        if group:
            stmt = stmt.where(CatalogMetaColorPalette.group == group)
        stmt = stmt.order_by(
            CatalogMetaColorPalette.group.asc(),
            CatalogMetaColorPalette.sort_order.asc(),
            CatalogMetaColorPalette.key.asc(),
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def create(
        db: Session,
        *,
        user: User,
        key: str,
        group: str,
        color_hex: str,
        description: str | None,
        sort_order: int,
    ) -> CatalogMetaColorPalette:
        row = CatalogMetaColorPalette(
            key=key,
            group=group,
            color_hex=color_hex,
            description=description,
            sort_order=sort_order,
            modified_by=user.id,
        )
        db.add(row)
        try:
            db.flush()  # obtener id
            _write_audit(
                db,
                table_name="catalog_meta_color_palette",
                row_id=row.id,
                action="INSERT",
                diff={"after": _snapshot(row, _COLOR_FIELDS)},
                changed_by=user.id,
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ConflictError(
                f"Ya existe un color con group={group!r} key={key!r}."
            ) from exc
        db.refresh(row)
        bump_version()
        return row

    @staticmethod
    def update(
        db: Session,
        *,
        user: User,
        color_id: int,
        color_hex: str | None,
        description: str | None | object = ...,
        sort_order: int | None,
    ) -> CatalogMetaColorPalette:
        row = db.get(CatalogMetaColorPalette, color_id)
        if row is None:
            raise NotFoundError(f"Color id={color_id} no encontrado.")
        before = _snapshot(row, _COLOR_FIELDS)
        if color_hex is not None:
            row.color_hex = color_hex
        if description is not ...:
            row.description = description  # type: ignore[assignment]
        if sort_order is not None:
            row.sort_order = sort_order
        row.modified_by = user.id
        after = _snapshot(row, _COLOR_FIELDS)
        changed = {k: after[k] for k in after if after[k] != before[k]}
        if changed:
            _write_audit(
                db,
                table_name="catalog_meta_color_palette",
                row_id=row.id,
                action="UPDATE",
                diff={"before": {k: before[k] for k in changed}, "after": changed},
                changed_by=user.id,
            )
        db.commit()
        db.refresh(row)
        bump_version()
        return row

    @staticmethod
    def delete(db: Session, *, user: User, color_id: int) -> None:
        row = db.get(CatalogMetaColorPalette, color_id)
        if row is None:
            raise NotFoundError(f"Color id={color_id} no encontrado.")
        snapshot = _snapshot(row, _COLOR_FIELDS)
        row_id = row.id
        db.delete(row)
        _write_audit(
            db,
            table_name="catalog_meta_color_palette",
            row_id=row_id,
            action="DELETE",
            diff={"before": snapshot},
            changed_by=user.id,
        )
        db.commit()
        bump_version()


class CatalogMetaLabelService:
    """CRUD de ``catalog_meta_label``."""

    @staticmethod
    def list(
        db: Session,
        *,
        search: str | None = None,
        category: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[CatalogMetaLabel], int]:
        stmt = select(CatalogMetaLabel)
        count_stmt = select(func.count()).select_from(CatalogMetaLabel)
        if category:
            stmt = stmt.where(CatalogMetaLabel.category == category)
            count_stmt = count_stmt.where(CatalogMetaLabel.category == category)
        if search:
            term = f"%{search.strip()}%"
            clause = or_(
                CatalogMetaLabel.code.ilike(term),
                CatalogMetaLabel.label_es.ilike(term),
                CatalogMetaLabel.label_en.ilike(term),
            )
            stmt = stmt.where(clause)
            count_stmt = count_stmt.where(clause)

        total = db.execute(count_stmt).scalar_one()
        stmt = (
            stmt.order_by(
                CatalogMetaLabel.category.asc().nulls_last(),
                CatalogMetaLabel.sort_order.asc(),
                CatalogMetaLabel.code.asc(),
            )
            .offset(max(0, offset))
            .limit(max(1, min(limit, 500)))
        )
        items = list(db.execute(stmt).scalars().all())
        return items, int(total)

    @staticmethod
    def list_categories(db: Session) -> list[str]:
        rows = db.execute(
            select(CatalogMetaLabel.category)
            .where(CatalogMetaLabel.category.is_not(None))
            .distinct()
            .order_by(CatalogMetaLabel.category.asc())
        ).all()
        return [r[0] for r in rows if r[0] is not None]

    @staticmethod
    def create(
        db: Session,
        *,
        user: User,
        code: str,
        label_es: str,
        label_en: str | None,
        category: str | None,
        sort_order: int,
    ) -> CatalogMetaLabel:
        row = CatalogMetaLabel(
            code=code,
            label_es=label_es,
            label_en=label_en,
            category=category,
            sort_order=sort_order,
            modified_by=user.id,
        )
        db.add(row)
        try:
            db.flush()
            _write_audit(
                db,
                table_name="catalog_meta_label",
                row_id=row.id,
                action="INSERT",
                diff={"after": _snapshot(row, _LABEL_FIELDS)},
                changed_by=user.id,
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ConflictError(f"Ya existe un label con code={code!r}.") from exc
        db.refresh(row)
        bump_version()
        return row

    @staticmethod
    def update(
        db: Session,
        *,
        user: User,
        label_id: int,
        label_es: str | None,
        label_en: str | None | object = ...,
        category: str | None | object = ...,
        sort_order: int | None,
    ) -> CatalogMetaLabel:
        row = db.get(CatalogMetaLabel, label_id)
        if row is None:
            raise NotFoundError(f"Label id={label_id} no encontrado.")
        before = _snapshot(row, _LABEL_FIELDS)
        if label_es is not None:
            row.label_es = label_es
        if label_en is not ...:
            row.label_en = label_en  # type: ignore[assignment]
        if category is not ...:
            row.category = category  # type: ignore[assignment]
        if sort_order is not None:
            row.sort_order = sort_order
        row.modified_by = user.id
        after = _snapshot(row, _LABEL_FIELDS)
        changed = {k: after[k] for k in after if after[k] != before[k]}
        if changed:
            _write_audit(
                db,
                table_name="catalog_meta_label",
                row_id=row.id,
                action="UPDATE",
                diff={"before": {k: before[k] for k in changed}, "after": changed},
                changed_by=user.id,
            )
        db.commit()
        db.refresh(row)
        bump_version()
        return row

    @staticmethod
    def delete(db: Session, *, user: User, label_id: int) -> None:
        row = db.get(CatalogMetaLabel, label_id)
        if row is None:
            raise NotFoundError(f"Label id={label_id} no encontrado.")
        snapshot = _snapshot(row, _LABEL_FIELDS)
        row_id = row.id
        db.delete(row)
        _write_audit(
            db,
            table_name="catalog_meta_label",
            row_id=row_id,
            action="DELETE",
            diff={"before": snapshot},
            changed_by=user.id,
        )
        db.commit()
        bump_version()


class CatalogMetaAuditService:
    """Lectura del historial global (``catalog_meta_audit``)."""

    @staticmethod
    def list(
        db: Session,
        *,
        table_name: str | None = None,
        action: str | None = None,
        row_id: int | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int, list[str]]:
        stmt = select(CatalogMetaAudit, CoreUser.username).outerjoin(
            CoreUser, CatalogMetaAudit.changed_by == CoreUser.id
        )
        count_stmt = select(func.count()).select_from(CatalogMetaAudit)
        if table_name:
            stmt = stmt.where(CatalogMetaAudit.table_name == table_name)
            count_stmt = count_stmt.where(CatalogMetaAudit.table_name == table_name)
        if action:
            stmt = stmt.where(CatalogMetaAudit.action == action)
            count_stmt = count_stmt.where(CatalogMetaAudit.action == action)
        if row_id is not None:
            stmt = stmt.where(CatalogMetaAudit.row_id == row_id)
            count_stmt = count_stmt.where(CatalogMetaAudit.row_id == row_id)

        total = db.execute(count_stmt).scalar_one()

        stmt = (
            stmt.order_by(CatalogMetaAudit.changed_at.desc())
            .offset(max(0, offset))
            .limit(max(1, min(limit, 500)))
        )
        rows = db.execute(stmt).all()
        items = [
            {
                "id": a.id,
                "table_name": a.table_name,
                "row_id": a.row_id,
                "action": a.action,
                "diff_json": a.diff_json,
                "changed_by_username": username,
                "changed_at": a.changed_at,
            }
            for (a, username) in rows
        ]

        tables = [
            r[0]
            for r in db.execute(
                select(CatalogMetaAudit.table_name)
                .distinct()
                .order_by(CatalogMetaAudit.table_name)
            ).all()
        ]
        return items, int(total), tables


# ---------------------------------------------------------------------------
#  Sector mapping + tech family (Fase 3.3.C)
# ---------------------------------------------------------------------------

_SECTOR_FIELDS = ("tech_prefix", "sector_name", "sort_order")
_FAMILY_FIELDS = ("family_code", "tech_prefix", "sort_order")


class CatalogMetaSectorService:
    """CRUD de ``catalog_meta_sector_mapping``."""

    @staticmethod
    def list(db: Session) -> list[CatalogMetaSectorMapping]:
        return list(
            db.execute(
                select(CatalogMetaSectorMapping).order_by(
                    CatalogMetaSectorMapping.sort_order.asc(),
                    CatalogMetaSectorMapping.tech_prefix.asc(),
                )
            ).scalars().all()
        )

    @staticmethod
    def create(
        db: Session,
        *,
        user: User,
        tech_prefix: str,
        sector_name: str,
        sort_order: int,
    ) -> CatalogMetaSectorMapping:
        row = CatalogMetaSectorMapping(
            tech_prefix=tech_prefix,
            sector_name=sector_name,
            sort_order=sort_order,
            modified_by=user.id,
        )
        db.add(row)
        try:
            db.flush()
            _write_audit(
                db,
                table_name="catalog_meta_sector_mapping",
                row_id=row.id,
                action="INSERT",
                diff={"after": _snapshot(row, _SECTOR_FIELDS)},
                changed_by=user.id,
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ConflictError(
                f"Ya existe un mapeo para tech_prefix={tech_prefix!r}."
            ) from exc
        db.refresh(row)
        bump_version()
        return row

    @staticmethod
    def update(
        db: Session,
        *,
        user: User,
        row_id: int,
        sector_name: str | None,
        sort_order: int | None,
    ) -> CatalogMetaSectorMapping:
        row = db.get(CatalogMetaSectorMapping, row_id)
        if row is None:
            raise NotFoundError(f"Sector mapping id={row_id} no encontrado.")
        before = _snapshot(row, _SECTOR_FIELDS)
        if sector_name is not None:
            row.sector_name = sector_name
        if sort_order is not None:
            row.sort_order = sort_order
        row.modified_by = user.id
        after = _snapshot(row, _SECTOR_FIELDS)
        changed = {k: after[k] for k in after if after[k] != before[k]}
        if changed:
            _write_audit(
                db,
                table_name="catalog_meta_sector_mapping",
                row_id=row.id,
                action="UPDATE",
                diff={"before": {k: before[k] for k in changed}, "after": changed},
                changed_by=user.id,
            )
        db.commit()
        db.refresh(row)
        bump_version()
        return row

    @staticmethod
    def delete(db: Session, *, user: User, row_id: int) -> None:
        row = db.get(CatalogMetaSectorMapping, row_id)
        if row is None:
            raise NotFoundError(f"Sector mapping id={row_id} no encontrado.")
        snap = _snapshot(row, _SECTOR_FIELDS)
        rid = row.id
        db.delete(row)
        _write_audit(
            db,
            table_name="catalog_meta_sector_mapping",
            row_id=rid,
            action="DELETE",
            diff={"before": snap},
            changed_by=user.id,
        )
        db.commit()
        bump_version()


class CatalogMetaTechFamilyService:
    """CRUD de ``catalog_meta_tech_family``."""

    @staticmethod
    def list(
        db: Session,
        *,
        family_code: str | None = None,
    ) -> tuple[list[CatalogMetaTechFamily], list[str]]:
        stmt = select(CatalogMetaTechFamily)
        if family_code:
            stmt = stmt.where(CatalogMetaTechFamily.family_code == family_code)
        stmt = stmt.order_by(
            CatalogMetaTechFamily.family_code.asc(),
            CatalogMetaTechFamily.sort_order.asc(),
            CatalogMetaTechFamily.tech_prefix.asc(),
        )
        items = list(db.execute(stmt).scalars().all())
        families = [
            r[0]
            for r in db.execute(
                select(CatalogMetaTechFamily.family_code)
                .distinct()
                .order_by(CatalogMetaTechFamily.family_code.asc())
            ).all()
        ]
        return items, families

    @staticmethod
    def create(
        db: Session,
        *,
        user: User,
        family_code: str,
        tech_prefix: str,
        sort_order: int,
    ) -> CatalogMetaTechFamily:
        row = CatalogMetaTechFamily(
            family_code=family_code,
            tech_prefix=tech_prefix,
            sort_order=sort_order,
            modified_by=user.id,
        )
        db.add(row)
        try:
            db.flush()
            _write_audit(
                db,
                table_name="catalog_meta_tech_family",
                row_id=row.id,
                action="INSERT",
                diff={"after": _snapshot(row, _FAMILY_FIELDS)},
                changed_by=user.id,
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ConflictError(
                f"Ya existe {family_code!r}/{tech_prefix!r}."
            ) from exc
        db.refresh(row)
        bump_version()
        return row

    @staticmethod
    def bulk_add(
        db: Session,
        *,
        user: User,
        family_code: str,
        tech_prefixes: list[str],
    ) -> list[CatalogMetaTechFamily]:
        """Agrega N prefijos a una familia. Ignora duplicados existentes."""
        existing = set(
            r[0]
            for r in db.execute(
                select(CatalogMetaTechFamily.tech_prefix).where(
                    CatalogMetaTechFamily.family_code == family_code
                )
            ).all()
        )
        current_max = db.execute(
            select(func.coalesce(func.max(CatalogMetaTechFamily.sort_order), -1)).where(
                CatalogMetaTechFamily.family_code == family_code
            )
        ).scalar_one()
        added: list[CatalogMetaTechFamily] = []
        for p in tech_prefixes:
            p = p.strip()
            if not p or p in existing:
                continue
            current_max = int(current_max) + 1
            row = CatalogMetaTechFamily(
                family_code=family_code,
                tech_prefix=p,
                sort_order=current_max,
                modified_by=user.id,
            )
            db.add(row)
            db.flush()
            _write_audit(
                db,
                table_name="catalog_meta_tech_family",
                row_id=row.id,
                action="INSERT",
                diff={"after": _snapshot(row, _FAMILY_FIELDS)},
                changed_by=user.id,
            )
            added.append(row)
            existing.add(p)
        db.commit()
        for r in added:
            db.refresh(r)
        if added:
            bump_version()
        return added

    @staticmethod
    def update(
        db: Session,
        *,
        user: User,
        row_id: int,
        sort_order: int | None,
    ) -> CatalogMetaTechFamily:
        row = db.get(CatalogMetaTechFamily, row_id)
        if row is None:
            raise NotFoundError(f"Tech family id={row_id} no encontrado.")
        before = _snapshot(row, _FAMILY_FIELDS)
        if sort_order is not None:
            row.sort_order = sort_order
        row.modified_by = user.id
        after = _snapshot(row, _FAMILY_FIELDS)
        changed = {k: after[k] for k in after if after[k] != before[k]}
        if changed:
            _write_audit(
                db,
                table_name="catalog_meta_tech_family",
                row_id=row.id,
                action="UPDATE",
                diff={"before": {k: before[k] for k in changed}, "after": changed},
                changed_by=user.id,
            )
        db.commit()
        db.refresh(row)
        bump_version()
        return row

    @staticmethod
    def delete(db: Session, *, user: User, row_id: int) -> None:
        row = db.get(CatalogMetaTechFamily, row_id)
        if row is None:
            raise NotFoundError(f"Tech family id={row_id} no encontrado.")
        snap = _snapshot(row, _FAMILY_FIELDS)
        rid = row.id
        db.delete(row)
        _write_audit(
            db,
            table_name="catalog_meta_tech_family",
            row_id=rid,
            action="DELETE",
            diff={"before": snap},
            changed_by=user.id,
        )
        db.commit()
        bump_version()


# ---------------------------------------------------------------------------
#  Chart modules / submodules (Fase 3.3.D)
# ---------------------------------------------------------------------------

_MODULE_FIELDS = ("code", "label", "icon", "sort_order", "is_visible")
_SUBMODULE_FIELDS = ("module_id", "code", "label", "icon", "sort_order", "is_visible")


class CatalogMetaModuleService:
    """CRUD de módulos + submódulos con tree."""

    @staticmethod
    def tree(db: Session) -> list[dict[str, Any]]:
        """Retorna la jerarquía completa con submódulos anidados y conteo de charts."""
        modules = list(
            db.execute(
                select(CatalogMetaChartModule).order_by(CatalogMetaChartModule.sort_order.asc())
            ).scalars().all()
        )
        submodules = list(
            db.execute(
                select(CatalogMetaChartSubmodule).order_by(CatalogMetaChartSubmodule.sort_order.asc())
            ).scalars().all()
        )
        chart_counts_rows = db.execute(
            select(
                CatalogMetaChartConfig.module_id,
                func.count(CatalogMetaChartConfig.id),
            ).group_by(CatalogMetaChartConfig.module_id)
        ).all()
        chart_counts = {int(mid): int(n) for mid, n in chart_counts_rows}

        subs_by_module: dict[int, list[CatalogMetaChartSubmodule]] = {}
        for s in submodules:
            subs_by_module.setdefault(s.module_id, []).append(s)

        out: list[dict[str, Any]] = []
        for m in modules:
            out.append(
                {
                    "id": m.id,
                    "code": m.code,
                    "label": m.label,
                    "icon": m.icon,
                    "sort_order": m.sort_order,
                    "is_visible": bool(m.is_visible),
                    "updated_at": m.updated_at,
                    "chart_count": chart_counts.get(m.id, 0),
                    "submodules": [
                        {
                            "id": s.id,
                            "module_id": s.module_id,
                            "code": s.code,
                            "label": s.label,
                            "icon": s.icon,
                            "sort_order": s.sort_order,
                            "is_visible": bool(s.is_visible),
                            "updated_at": s.updated_at,
                        }
                        for s in subs_by_module.get(m.id, [])
                    ],
                }
            )
        return out

    # -- Módulos ------------------------------------------------------------

    @staticmethod
    def create_module(
        db: Session,
        *,
        user: User,
        code: str,
        label: str,
        icon: str | None,
        sort_order: int,
        is_visible: bool,
    ) -> CatalogMetaChartModule:
        row = CatalogMetaChartModule(
            code=code,
            label=label,
            icon=icon,
            sort_order=sort_order,
            is_visible=is_visible,
            modified_by=user.id,
        )
        db.add(row)
        try:
            db.flush()
            _write_audit(
                db,
                table_name="catalog_meta_chart_module",
                row_id=row.id,
                action="INSERT",
                diff={"after": _snapshot(row, _MODULE_FIELDS)},
                changed_by=user.id,
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ConflictError(f"Ya existe un módulo con code={code!r}.") from exc
        db.refresh(row)
        bump_version()
        return row

    @staticmethod
    def update_module(
        db: Session,
        *,
        user: User,
        row_id: int,
        label: str | None,
        icon: str | None | object = ...,
        sort_order: int | None,
        is_visible: bool | None,
    ) -> CatalogMetaChartModule:
        row = db.get(CatalogMetaChartModule, row_id)
        if row is None:
            raise NotFoundError(f"Módulo id={row_id} no encontrado.")
        before = _snapshot(row, _MODULE_FIELDS)
        if label is not None:
            row.label = label
        if icon is not ...:
            row.icon = icon  # type: ignore[assignment]
        if sort_order is not None:
            row.sort_order = sort_order
        if is_visible is not None:
            row.is_visible = is_visible
        row.modified_by = user.id
        after = _snapshot(row, _MODULE_FIELDS)
        changed = {k: after[k] for k in after if after[k] != before[k]}
        if changed:
            _write_audit(
                db,
                table_name="catalog_meta_chart_module",
                row_id=row.id,
                action="UPDATE",
                diff={"before": {k: before[k] for k in changed}, "after": changed},
                changed_by=user.id,
            )
        db.commit()
        db.refresh(row)
        bump_version()
        return row

    @staticmethod
    def delete_module(db: Session, *, user: User, row_id: int) -> None:
        row = db.get(CatalogMetaChartModule, row_id)
        if row is None:
            raise NotFoundError(f"Módulo id={row_id} no encontrado.")
        # Chequeo: no eliminar si tiene charts asociados.
        n = db.execute(
            select(func.count()).select_from(CatalogMetaChartConfig).where(
                CatalogMetaChartConfig.module_id == row.id
            )
        ).scalar_one()
        if int(n) > 0:
            raise ConflictError(
                f"El módulo tiene {n} gráficas asociadas. Muévelas a otro módulo primero."
            )
        snap = _snapshot(row, _MODULE_FIELDS)
        rid = row.id
        db.delete(row)
        _write_audit(
            db,
            table_name="catalog_meta_chart_module",
            row_id=rid,
            action="DELETE",
            diff={"before": snap},
            changed_by=user.id,
        )
        db.commit()
        bump_version()

    # -- Submódulos ---------------------------------------------------------

    @staticmethod
    def create_submodule(
        db: Session,
        *,
        user: User,
        module_id: int,
        code: str,
        label: str,
        icon: str | None,
        sort_order: int,
        is_visible: bool,
    ) -> CatalogMetaChartSubmodule:
        # Validar que el módulo exista.
        if db.get(CatalogMetaChartModule, module_id) is None:
            raise NotFoundError(f"Módulo id={module_id} no encontrado.")
        row = CatalogMetaChartSubmodule(
            module_id=module_id,
            code=code,
            label=label,
            icon=icon,
            sort_order=sort_order,
            is_visible=is_visible,
            modified_by=user.id,
        )
        db.add(row)
        try:
            db.flush()
            _write_audit(
                db,
                table_name="catalog_meta_chart_submodule",
                row_id=row.id,
                action="INSERT",
                diff={"after": _snapshot(row, _SUBMODULE_FIELDS)},
                changed_by=user.id,
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ConflictError(
                f"Ya existe un submódulo con module_id={module_id} code={code!r}."
            ) from exc
        db.refresh(row)
        bump_version()
        return row

    @staticmethod
    def update_submodule(
        db: Session,
        *,
        user: User,
        row_id: int,
        module_id: int | None,
        label: str | None,
        icon: str | None | object = ...,
        sort_order: int | None,
        is_visible: bool | None,
    ) -> CatalogMetaChartSubmodule:
        row = db.get(CatalogMetaChartSubmodule, row_id)
        if row is None:
            raise NotFoundError(f"Submódulo id={row_id} no encontrado.")
        before = _snapshot(row, _SUBMODULE_FIELDS)
        if module_id is not None:
            if db.get(CatalogMetaChartModule, module_id) is None:
                raise NotFoundError(f"Módulo id={module_id} no encontrado.")
            row.module_id = module_id
        if label is not None:
            row.label = label
        if icon is not ...:
            row.icon = icon  # type: ignore[assignment]
        if sort_order is not None:
            row.sort_order = sort_order
        if is_visible is not None:
            row.is_visible = is_visible
        row.modified_by = user.id
        after = _snapshot(row, _SUBMODULE_FIELDS)
        changed = {k: after[k] for k in after if after[k] != before[k]}
        if changed:
            _write_audit(
                db,
                table_name="catalog_meta_chart_submodule",
                row_id=row.id,
                action="UPDATE",
                diff={"before": {k: before[k] for k in changed}, "after": changed},
                changed_by=user.id,
            )
        db.commit()
        db.refresh(row)
        bump_version()
        return row

    @staticmethod
    def delete_submodule(db: Session, *, user: User, row_id: int) -> None:
        row = db.get(CatalogMetaChartSubmodule, row_id)
        if row is None:
            raise NotFoundError(f"Submódulo id={row_id} no encontrado.")
        # Cualquier chart vinculado queda con submodule_id=NULL por ON DELETE SET NULL.
        snap = _snapshot(row, _SUBMODULE_FIELDS)
        rid = row.id
        db.delete(row)
        _write_audit(
            db,
            table_name="catalog_meta_chart_submodule",
            row_id=rid,
            action="DELETE",
            diff={"before": snap},
            changed_by=user.id,
        )
        db.commit()
        bump_version()


# ---------------------------------------------------------------------------
#  Variable units (Fase 3.3.E)
# ---------------------------------------------------------------------------

_UNIT_FIELDS = ("variable_name", "unit_base", "display_units_json")


class CatalogMetaVariableUnitService:
    @staticmethod
    def list(db: Session) -> list[CatalogMetaVariableUnit]:
        return list(
            db.execute(
                select(CatalogMetaVariableUnit).order_by(CatalogMetaVariableUnit.variable_name.asc())
            ).scalars().all()
        )

    @staticmethod
    def create(
        db: Session,
        *,
        user: User,
        variable_name: str,
        unit_base: str,
        display_units_json: list[dict] | None,
    ) -> CatalogMetaVariableUnit:
        row = CatalogMetaVariableUnit(
            variable_name=variable_name,
            unit_base=unit_base,
            display_units_json=display_units_json,
            modified_by=user.id,
        )
        db.add(row)
        try:
            db.flush()
            _write_audit(
                db,
                table_name="catalog_meta_variable_unit",
                row_id=row.id,
                action="INSERT",
                diff={"after": _snapshot(row, _UNIT_FIELDS)},
                changed_by=user.id,
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ConflictError(
                f"Ya existe unidad para variable {variable_name!r}."
            ) from exc
        db.refresh(row)
        bump_version()
        return row

    @staticmethod
    def update(
        db: Session,
        *,
        user: User,
        row_id: int,
        unit_base: str | None,
        display_units_json: list[dict] | None | object = ...,
    ) -> CatalogMetaVariableUnit:
        row = db.get(CatalogMetaVariableUnit, row_id)
        if row is None:
            raise NotFoundError(f"Variable unit id={row_id} no encontrado.")
        before = _snapshot(row, _UNIT_FIELDS)
        if unit_base is not None:
            row.unit_base = unit_base
        if display_units_json is not ...:
            row.display_units_json = display_units_json  # type: ignore[assignment]
        row.modified_by = user.id
        after = _snapshot(row, _UNIT_FIELDS)
        changed = {k: after[k] for k in after if after[k] != before[k]}
        if changed:
            _write_audit(
                db,
                table_name="catalog_meta_variable_unit",
                row_id=row.id,
                action="UPDATE",
                diff={"before": {k: before[k] for k in changed}, "after": changed},
                changed_by=user.id,
            )
        db.commit()
        db.refresh(row)
        bump_version()
        return row

    @staticmethod
    def delete(db: Session, *, user: User, row_id: int) -> None:
        row = db.get(CatalogMetaVariableUnit, row_id)
        if row is None:
            raise NotFoundError(f"Variable unit id={row_id} no encontrado.")
        snap = _snapshot(row, _UNIT_FIELDS)
        rid = row.id
        db.delete(row)
        _write_audit(
            db,
            table_name="catalog_meta_variable_unit",
            row_id=rid,
            action="DELETE",
            diff={"before": snap},
            changed_by=user.id,
        )
        db.commit()
        bump_version()


# ---------------------------------------------------------------------------
#  Chart config (Fase 3.3.F) + sub-filtros (Fase 3.3.H)
# ---------------------------------------------------------------------------

_CHART_CFG_FIELDS = (
    "tipo", "module_id", "submodule_id", "label_titulo", "label_figura",
    "variable_default", "filtro_kind", "filtro_params_json",
    "agrupar_por_default", "agrupaciones_permitidas_json",
    "color_fn_key", "flags_json", "msg_sin_datos",
    "data_explorer_filters_json", "is_visible", "sort_order",
)

_SUBFILTER_FIELDS = (
    "chart_id", "group_label", "code", "display_label", "sort_order", "default_selected",
)


def _chart_to_public(row: CatalogMetaChartConfig, subs: list[CatalogMetaChartSubfilter]) -> dict[str, Any]:
    return {
        "id": row.id,
        "tipo": row.tipo,
        "module_id": row.module_id,
        "submodule_id": row.submodule_id,
        "label_titulo": row.label_titulo,
        "label_figura": row.label_figura,
        "variable_default": row.variable_default,
        "filtro_kind": row.filtro_kind,
        "filtro_params_json": row.filtro_params_json,
        "agrupar_por_default": row.agrupar_por_default,
        "agrupaciones_permitidas_json": row.agrupaciones_permitidas_json,
        "color_fn_key": row.color_fn_key,
        "flags_json": row.flags_json,
        "msg_sin_datos": row.msg_sin_datos,
        "data_explorer_filters_json": row.data_explorer_filters_json,
        "is_visible": bool(row.is_visible),
        "sort_order": row.sort_order,
        "subfilters": [
            {
                "id": s.id,
                "chart_id": s.chart_id,
                "group_label": s.group_label,
                "code": s.code,
                "display_label": s.display_label,
                "sort_order": s.sort_order,
                "default_selected": bool(s.default_selected),
            }
            for s in subs
        ],
        "updated_at": row.updated_at,
    }


class CatalogMetaChartConfigService:
    """CRUD de catalog_meta_chart_config + sub-filtros."""

    @staticmethod
    def list(
        db: Session,
        *,
        module_id: int | None = None,
    ) -> list[dict[str, Any]]:
        stmt = select(CatalogMetaChartConfig)
        if module_id is not None:
            stmt = stmt.where(CatalogMetaChartConfig.module_id == module_id)
        stmt = stmt.order_by(
            CatalogMetaChartConfig.module_id.asc(),
            CatalogMetaChartConfig.submodule_id.asc().nulls_first(),
            CatalogMetaChartConfig.sort_order.asc(),
            CatalogMetaChartConfig.tipo.asc(),
        )
        charts = list(db.execute(stmt).scalars().all())
        if not charts:
            return []
        ids = [c.id for c in charts]
        subs = list(
            db.execute(
                select(CatalogMetaChartSubfilter)
                .where(CatalogMetaChartSubfilter.chart_id.in_(ids))
                .order_by(CatalogMetaChartSubfilter.chart_id.asc(), CatalogMetaChartSubfilter.sort_order.asc())
            ).scalars().all()
        )
        subs_by_chart: dict[int, list[CatalogMetaChartSubfilter]] = {}
        for s in subs:
            subs_by_chart.setdefault(s.chart_id, []).append(s)
        return [_chart_to_public(c, subs_by_chart.get(c.id, [])) for c in charts]

    @staticmethod
    def create(
        db: Session,
        *,
        user: User,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        row = CatalogMetaChartConfig(
            tipo=payload["tipo"],
            module_id=payload["module_id"],
            submodule_id=payload.get("submodule_id"),
            label_titulo=payload["label_titulo"],
            label_figura=payload.get("label_figura"),
            variable_default=payload["variable_default"],
            filtro_kind=payload.get("filtro_kind", "prefix"),
            filtro_params_json=payload.get("filtro_params_json"),
            agrupar_por_default=payload.get("agrupar_por_default", "TECNOLOGIA"),
            agrupaciones_permitidas_json=payload.get("agrupaciones_permitidas_json"),
            color_fn_key=payload.get("color_fn_key", "tecnologias"),
            flags_json=payload.get("flags_json"),
            msg_sin_datos=payload.get("msg_sin_datos"),
            data_explorer_filters_json=payload.get("data_explorer_filters_json"),
            is_visible=payload.get("is_visible", True),
            sort_order=payload.get("sort_order", 0),
            modified_by=user.id,
        )
        db.add(row)
        try:
            db.flush()
            _write_audit(
                db,
                table_name="catalog_meta_chart_config",
                row_id=row.id,
                action="INSERT",
                diff={"after": _snapshot(row, _CHART_CFG_FIELDS)},
                changed_by=user.id,
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ConflictError(f"Ya existe un chart con tipo={payload['tipo']!r}.") from exc
        db.refresh(row)
        bump_version()
        return _chart_to_public(row, [])

    @staticmethod
    def update(
        db: Session,
        *,
        user: User,
        row_id: int,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        row = db.get(CatalogMetaChartConfig, row_id)
        if row is None:
            raise NotFoundError(f"Chart config id={row_id} no encontrado.")
        before = _snapshot(row, _CHART_CFG_FIELDS)
        for field, value in patch.items():
            if field not in _CHART_CFG_FIELDS:
                continue
            if field == "tipo":
                continue  # tipo es inmutable
            setattr(row, field, value)
        row.modified_by = user.id
        after = _snapshot(row, _CHART_CFG_FIELDS)
        changed = {k: after[k] for k in after if after[k] != before[k]}
        if changed:
            _write_audit(
                db,
                table_name="catalog_meta_chart_config",
                row_id=row.id,
                action="UPDATE",
                diff={"before": {k: before[k] for k in changed}, "after": changed},
                changed_by=user.id,
            )
        db.commit()
        db.refresh(row)
        subs = list(
            db.execute(
                select(CatalogMetaChartSubfilter)
                .where(CatalogMetaChartSubfilter.chart_id == row.id)
                .order_by(CatalogMetaChartSubfilter.sort_order.asc())
            ).scalars().all()
        )
        bump_version()
        return _chart_to_public(row, subs)

    @staticmethod
    def delete(db: Session, *, user: User, row_id: int) -> None:
        row = db.get(CatalogMetaChartConfig, row_id)
        if row is None:
            raise NotFoundError(f"Chart config id={row_id} no encontrado.")
        snap = _snapshot(row, _CHART_CFG_FIELDS)
        rid = row.id
        db.delete(row)
        _write_audit(
            db,
            table_name="catalog_meta_chart_config",
            row_id=rid,
            action="DELETE",
            diff={"before": snap},
            changed_by=user.id,
        )
        db.commit()
        bump_version()

    # -- Sub-filtros --------------------------------------------------------

    @staticmethod
    def create_subfilter(
        db: Session,
        *,
        user: User,
        chart_id: int,
        group_label: str | None,
        code: str,
        display_label: str | None,
        sort_order: int,
        default_selected: bool,
    ) -> CatalogMetaChartSubfilter:
        if db.get(CatalogMetaChartConfig, chart_id) is None:
            raise NotFoundError(f"Chart id={chart_id} no encontrado.")
        row = CatalogMetaChartSubfilter(
            chart_id=chart_id,
            group_label=group_label,
            code=code,
            display_label=display_label,
            sort_order=sort_order,
            default_selected=default_selected,
            modified_by=user.id,
        )
        db.add(row)
        try:
            db.flush()
            _write_audit(
                db,
                table_name="catalog_meta_chart_subfilter",
                row_id=row.id,
                action="INSERT",
                diff={"after": _snapshot(row, _SUBFILTER_FIELDS)},
                changed_by=user.id,
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ConflictError(f"Ya existe sub-filtro code={code!r} para chart.") from exc
        db.refresh(row)
        bump_version()
        return row

    @staticmethod
    def update_subfilter(
        db: Session,
        *,
        user: User,
        row_id: int,
        patch: dict[str, Any],
    ) -> CatalogMetaChartSubfilter:
        row = db.get(CatalogMetaChartSubfilter, row_id)
        if row is None:
            raise NotFoundError(f"Sub-filtro id={row_id} no encontrado.")
        before = _snapshot(row, _SUBFILTER_FIELDS)
        for field, value in patch.items():
            if field in _SUBFILTER_FIELDS and field not in ("chart_id", "code"):
                setattr(row, field, value)
        row.modified_by = user.id
        after = _snapshot(row, _SUBFILTER_FIELDS)
        changed = {k: after[k] for k in after if after[k] != before[k]}
        if changed:
            _write_audit(
                db,
                table_name="catalog_meta_chart_subfilter",
                row_id=row.id,
                action="UPDATE",
                diff={"before": {k: before[k] for k in changed}, "after": changed},
                changed_by=user.id,
            )
        db.commit()
        db.refresh(row)
        bump_version()
        return row

    @staticmethod
    def delete_subfilter(db: Session, *, user: User, row_id: int) -> None:
        row = db.get(CatalogMetaChartSubfilter, row_id)
        if row is None:
            raise NotFoundError(f"Sub-filtro id={row_id} no encontrado.")
        snap = _snapshot(row, _SUBFILTER_FIELDS)
        rid = row.id
        db.delete(row)
        _write_audit(
            db,
            table_name="catalog_meta_chart_subfilter",
            row_id=rid,
            action="DELETE",
            diff={"before": snap},
            changed_by=user.id,
        )
        db.commit()
        bump_version()
