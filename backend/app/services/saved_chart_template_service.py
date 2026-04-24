"""CRUD de plantillas de gráficas por usuario y generación de reportes (ZIP).

El reporte renderiza cada plantilla usando los mismos helpers que usa la
API de exportación individual/facetas (``chart_service.render_chart_visualization_bytes``
y ``chart_service.render_comparison_facet_figure_bytes``), luego comprime
todas las imágenes en un ZIP.
"""

from __future__ import annotations

import io
import logging
import re
import uuid
import zipfile
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models import (
    ReportTemplate,
    ReportTemplateFavorite,
    SavedChartTemplate,
    SavedChartTemplateFavorite,
    User,
)
from app.schemas.saved_chart_template import (
    ReportCategoryExport,
    ReportTemplateItem,
)
from app.services.simulation_service import SimulationService
from app.visualization import chart_service


logger = logging.getLogger(__name__)


def _slugify(text: str, max_len: int = 80) -> str:
    clean = "".join(c if c.isalnum() or c in (" ", "_", "-") else "_" for c in (text or ""))
    clean = re.sub(r"\s+", "_", clean).strip("_")
    return (clean or "grafica")[:max_len]


def _chart_to_public_dict(
    obj: SavedChartTemplate,
    *,
    current_user_id: uuid.UUID,
    owner_username: str | None,
    is_favorite: bool = False,
) -> dict:
    """Convierte ORM → dict para ``SavedChartTemplatePublic``, con is_owner."""
    return {
        "id": obj.id,
        "name": obj.name,
        "description": obj.description,
        "tipo": obj.tipo,
        "un": obj.un,
        "sub_filtro": obj.sub_filtro,
        "loc": obj.loc,
        "variable": obj.variable,
        "agrupar_por": obj.agrupar_por,
        "view_mode": obj.view_mode,
        "compare_mode": obj.compare_mode,
        "bar_orientation": obj.bar_orientation,
        "facet_placement": obj.facet_placement,
        "facet_legend_mode": obj.facet_legend_mode,
        "num_scenarios": obj.num_scenarios,
        "legend_title": obj.legend_title,
        "filename_mode": obj.filename_mode,
        "report_title": obj.report_title,
        "created_at": obj.created_at,
        "is_public": bool(getattr(obj, "is_public", False)),
        "owner_username": owner_username,
        "is_owner": obj.user_id == current_user_id,
        "is_favorite": bool(is_favorite),
    }


def _load_chart_favorite_ids(
    db: Session, *, user_id: uuid.UUID
) -> set[int]:
    rows = db.execute(
        select(SavedChartTemplateFavorite.template_id).where(
            SavedChartTemplateFavorite.user_id == user_id,
        )
    ).scalars().all()
    return {int(r) for r in rows}


def _load_report_favorite_ids(
    db: Session, *, user_id: uuid.UUID
) -> set[int]:
    rows = db.execute(
        select(ReportTemplateFavorite.report_id).where(
            ReportTemplateFavorite.user_id == user_id,
        )
    ).scalars().all()
    return {int(r) for r in rows}


class SavedChartTemplateService:
    # ---------------- CRUD ----------------

    @staticmethod
    def list_accessible(
        db: Session,
        *,
        user_id: uuid.UUID,
        current_user: User | None = None,
    ) -> list[dict]:
        """Propias + públicas de otros usuarios; anota is_owner/owner/is_favorite.

        Admin Reportes ve además todas las plantillas privadas ajenas (read-only),
        para poder abrir/editar reportes que las referencian.

        Orden: **favoritos primero**, luego propios, luego por fecha desc.
        """
        fav_ids = _load_chart_favorite_ids(db, user_id=user_id)
        is_admin_reports = bool(
            current_user is not None
            and (
                getattr(current_user, "is_admin_reports", False)
                or getattr(current_user, "can_manage_scenarios", False)
            )
        )
        visibility_filter = (
            None
            if is_admin_reports
            else or_(
                SavedChartTemplate.user_id == user_id,
                SavedChartTemplate.is_public.is_(True),
            )
        )
        stmt = (
            select(SavedChartTemplate, User.username)
            .join(User, User.id == SavedChartTemplate.user_id)
            .order_by(
                (SavedChartTemplate.user_id == user_id).desc(),
                SavedChartTemplate.created_at.desc(),
            )
        )
        if visibility_filter is not None:
            stmt = stmt.where(visibility_filter)
        rows = db.execute(stmt).all()
        out = [
            _chart_to_public_dict(
                obj,
                current_user_id=user_id,
                owner_username=username,
                is_favorite=int(obj.id) in fav_ids,
            )
            for obj, username in rows
        ]
        # Favoritos al tope manteniendo el orden relativo (stable sort).
        out.sort(key=lambda d: 0 if d.get("is_favorite") else 1)
        return out

    @staticmethod
    def get_accessible(
        db: Session,
        *,
        user_id: uuid.UUID,
        template_id: int,
        current_user: User | None = None,
    ) -> tuple[SavedChartTemplate, str | None]:
        """Devuelve (obj, owner_username) si el usuario la puede ver.

        Reglas:
          - dueño o plantilla pública → accesible;
          - Admin Reportes (``is_admin_reports`` o ``can_manage_scenarios``) →
            accede también a privadas ajenas (solo lectura — mutaciones siguen
            restringidas en ``update``/``delete``).
        """
        row = db.execute(
            select(SavedChartTemplate, User.username)
            .join(User, User.id == SavedChartTemplate.user_id)
            .where(SavedChartTemplate.id == template_id)
        ).one_or_none()
        if row is None:
            raise NotFoundError("Plantilla de gráfica no encontrada.")
        obj, username = row
        if obj.user_id != user_id and not bool(getattr(obj, "is_public", False)):
            is_admin_reports = bool(
                current_user is not None
                and (
                    getattr(current_user, "is_admin_reports", False)
                    or getattr(current_user, "can_manage_scenarios", False)
                )
            )
            if not is_admin_reports:
                raise NotFoundError("Plantilla de gráfica no encontrada.")
        return obj, username

    @staticmethod
    def get_for_user(
        db: Session, *, user_id: uuid.UUID, template_id: int
    ) -> SavedChartTemplate:
        """Dueño exclusivamente (para mutaciones)."""
        obj = db.get(SavedChartTemplate, template_id)
        if obj is None or obj.user_id != user_id:
            raise NotFoundError("Plantilla de gráfica no encontrada.")
        return obj

    @staticmethod
    def _resolve_owner_username(
        db: Session, *, user_id: uuid.UUID
    ) -> str | None:
        return db.scalar(select(User.username).where(User.id == user_id))

    @staticmethod
    def create(
        db: Session,
        *,
        user_id: uuid.UUID,
        payload: dict,
    ) -> dict:
        obj = SavedChartTemplate(user_id=user_id, **payload)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        username = SavedChartTemplateService._resolve_owner_username(
            db, user_id=user_id
        )
        return _chart_to_public_dict(
            obj,
            current_user_id=user_id,
            owner_username=username,
            is_favorite=False,
        )

    @staticmethod
    def update(
        db: Session,
        *,
        current_user: User,
        template_id: int,
        data: dict,
    ) -> dict:
        """Actualiza una plantilla.

        Reglas:
          - El dueño puede cambiar todos los campos.
          - Admin Reportes (``is_admin_reports`` o ``can_manage_scenarios``) puede
            cambiar únicamente ``report_title`` sobre plantillas accesibles
            (propias, públicas, o que él tenga visibilidad).
        """
        user_id = current_user.id
        # Carga con semántica "accesible" para permitir admin_reports sobre no-propias.
        row = db.execute(
            select(SavedChartTemplate, User.username)
            .join(User, User.id == SavedChartTemplate.user_id)
            .where(SavedChartTemplate.id == template_id)
        ).one_or_none()
        if row is None:
            raise NotFoundError("Plantilla de gráfica no encontrada.")
        obj, username = row
        is_owner = obj.user_id == user_id
        is_admin_reports = bool(
            getattr(current_user, "is_admin_reports", False)
            or getattr(current_user, "can_manage_scenarios", False)
        )
        is_public_template = bool(getattr(obj, "is_public", False))

        if not is_owner and not (is_admin_reports and is_public_template):
            raise NotFoundError("Plantilla de gráfica no encontrada.")

        touches_general = any(
            k in data for k in ("name", "description", "is_public")
        )
        if touches_general and not is_owner:
            raise ForbiddenError(
                "Solo el dueño puede cambiar nombre, descripción o visibilidad."
            )

        if "name" in data and data["name"] is not None:
            obj.name = str(data["name"]).strip()
        if "description" in data:
            obj.description = data["description"]
        if "is_public" in data and data["is_public"] is not None:
            obj.is_public = bool(data["is_public"])
        if "report_title" in data:
            raw = data["report_title"]
            cleaned = (raw or "").strip() if isinstance(raw, str) else None
            obj.report_title = cleaned if cleaned else None
        db.commit()
        db.refresh(obj)
        username = SavedChartTemplateService._resolve_owner_username(
            db, user_id=obj.user_id
        )
        fav = db.execute(
            select(SavedChartTemplateFavorite).where(
                SavedChartTemplateFavorite.user_id == user_id,
                SavedChartTemplateFavorite.template_id == template_id,
            )
        ).scalar_one_or_none()
        return _chart_to_public_dict(
            obj,
            current_user_id=user_id,
            owner_username=username,
            is_favorite=fav is not None,
        )

    @staticmethod
    def delete(db: Session, *, user_id: uuid.UUID, template_id: int) -> None:
        obj = SavedChartTemplateService.get_for_user(
            db, user_id=user_id, template_id=template_id
        )
        db.delete(obj)
        db.commit()

    # ---------------- Favoritos ----------------

    @staticmethod
    def set_favorite(
        db: Session,
        *,
        user_id: uuid.UUID,
        template_id: int,
        is_favorite: bool,
    ) -> dict:
        # Verifica accesibilidad (propia o pública).
        obj, username = SavedChartTemplateService.get_accessible(
            db, user_id=user_id, template_id=template_id
        )
        existing = db.execute(
            select(SavedChartTemplateFavorite).where(
                SavedChartTemplateFavorite.user_id == user_id,
                SavedChartTemplateFavorite.template_id == template_id,
            )
        ).scalar_one_or_none()
        if is_favorite and existing is None:
            db.add(
                SavedChartTemplateFavorite(
                    user_id=user_id, template_id=template_id,
                )
            )
            db.commit()
        elif not is_favorite and existing is not None:
            db.delete(existing)
            db.commit()
        return _chart_to_public_dict(
            obj,
            current_user_id=user_id,
            owner_username=username,
            is_favorite=bool(is_favorite),
        )

    # ---------------- Report generation ----------------

    @staticmethod
    def _render_template(
        db: Session,
        *,
        template: SavedChartTemplate,
        job_ids: list[int],
        fmt: str,
        job_display_overrides: dict[int, str] | None = None,
    ) -> tuple[bytes, str]:
        """Renderiza una plantilla y devuelve (bytes, extensión-sin-punto)."""
        if template.compare_mode == "facet":
            if len(job_ids) < 2:
                raise ValueError(
                    f"La plantilla '{template.name}' requiere al menos 2 escenarios."
                )
            facet_payload = chart_service.build_comparison_facet_data(
                db=db,
                job_ids=job_ids,
                tipo=template.tipo,
                un=template.un,
                sub_filtro=template.sub_filtro,
                loc=template.loc,
                variable=template.variable,
                agrupar_por=template.agrupar_por,
                job_display_overrides=job_display_overrides,
            )
            if not facet_payload.facets or not any(f.series for f in facet_payload.facets):
                raise ValueError(
                    f"Plantilla '{template.name}': sin datos con los filtros y escenarios seleccionados."
                )
            rt = (getattr(template, "report_title", None) or "").strip()
            if rt:
                facet_payload.title = rt
            img_bytes = chart_service.render_comparison_facet_figure_bytes(
                facet_payload,
                fmt=fmt,
                legend_title=template.legend_title,
            )
            return img_bytes, fmt

        # compare_mode == 'off' → single chart
        if len(job_ids) < 1:
            raise ValueError(
                f"La plantilla '{template.name}' requiere un escenario."
            )
        chart = chart_service.build_chart_data(
            db=db,
            job_id=job_ids[0],
            tipo=template.tipo,
            un=template.un,
            sub_filtro=template.sub_filtro,
            loc=template.loc,
            variable=template.variable,
            agrupar_por=template.agrupar_por,
        )
        if not chart.series:
            raise ValueError(
                f"Plantilla '{template.name}': sin datos con los filtros y escenario seleccionados."
            )
        rt = (getattr(template, "report_title", None) or "").strip()
        if rt:
            chart.title = rt
        img_bytes = chart_service.render_chart_visualization_bytes(
            chart,
            fmt=fmt,
            view_mode=template.view_mode or "column",
        )
        return img_bytes, fmt

    @staticmethod
    def _validate_access_jobs(
        db: Session,
        *,
        current_user: User,
        job_ids: list[int],
    ) -> None:
        for jid in job_ids:
            try:
                job = SimulationService.get_by_id(
                    db, current_user=current_user, job_id=jid
                )
            except NotFoundError as e:
                raise ForbiddenError(f"Job {jid} no encontrado o sin acceso.") from e
            if job["status"] != "SUCCEEDED":
                raise ValueError(f"Job {jid} no está en estado SUCCEEDED.")

    @staticmethod
    def _collect_items_from_categories(
        categories: list[ReportCategoryExport],
    ) -> list[ReportTemplateItem]:
        """Aplana el árbol de categorías a la lista de items (para validación)."""
        out: list[ReportTemplateItem] = []
        for cat in categories:
            out.extend(cat.items)
            for sub in cat.subcategories:
                out.extend(sub.items)
        return out

    @staticmethod
    def generate_report_zip(
        db: Session,
        *,
        current_user: User,
        items: list[ReportTemplateItem],
        fmt: str,
        organize_by_category: bool = False,
        categories: list[ReportCategoryExport] | None = None,
        job_display_overrides: dict[str, str] | None = None,
    ) -> tuple[io.BytesIO, str]:
        """Construye un ZIP con una imagen por plantilla.

        Dos modos:
          * Plano (default): itera ``items`` en orden, ``01_nombre.ext``, ...
          * Estructurado (``organize_by_category=True``): usa ``categories`` y
            genera rutas ``01_Categoria/[01_Sub/]01_nombre.ext``.
        """
        if fmt not in ("png", "svg"):
            raise ValueError("fmt debe ser 'png' o 'svg'")

        structured = organize_by_category and bool(categories)
        if structured:
            effective_items = SavedChartTemplateService._collect_items_from_categories(
                categories or []
            )
        else:
            effective_items = list(items)

        if not effective_items:
            raise ValueError("El reporte debe tener al menos una gráfica.")

        # Normalizar overrides: JSON trae claves como str; convertimos a int y
        # descartamos valores vacíos (para que caiga al display_name real).
        overrides_int: dict[int, str] | None = None
        if job_display_overrides:
            tmp: dict[int, str] = {}
            for k, v in job_display_overrides.items():
                try:
                    key = int(k)
                except (TypeError, ValueError):
                    continue
                clean = (v or "").strip()
                if clean:
                    tmp[key] = clean
            overrides_int = tmp or None

        # Validar todas las plantillas (incluyendo públicas) y accesos antes de renderizar.
        rendered_by_template: dict[int, tuple[SavedChartTemplate, list[int]]] = {}
        all_jobs: set[int] = set()
        for item in effective_items:
            template, _owner = SavedChartTemplateService.get_accessible(
                db, user_id=current_user.id, template_id=item.template_id
            )
            if len(item.job_ids) != template.num_scenarios:
                raise ValueError(
                    f"Plantilla '{template.name}' requiere {template.num_scenarios} escenario(s); "
                    f"recibidos {len(item.job_ids)}."
                )
            all_jobs.update(item.job_ids)
            # En modo estructurado una misma plantilla puede aparecer en varias
            # categorías; guardamos la última asignación (los job_ids deben
            # coincidir por coherencia del frontend, pero no lo forzamos).
            rendered_by_template[item.template_id] = (template, list(item.job_ids))

        SavedChartTemplateService._validate_access_jobs(
            db, current_user=current_user, job_ids=sorted(all_jobs)
        )

        buffer = io.BytesIO()
        used_names: dict[str, int] = {}
        manifest_lines: list[str] = [
            "Reporte generado con OSeMOSYS UPME",
            f"Usuario: {current_user.username}",
            f"Fecha: {datetime.now(timezone.utc).isoformat()}",
            f"Formato: {fmt}",
            f"Estructura: {'carpetas por categoría' if structured else 'plana'}",
            f"Plantillas: {len(rendered_by_template)}",
            "",
        ]

        def _write_one(
            zf: zipfile.ZipFile,
            *,
            idx: int,
            template: SavedChartTemplate,
            job_ids: list[int],
            folder: str,
            depth_prefix: str,
        ) -> str | None:
            """Renderiza y escribe una imagen; devuelve el arcname o None si fue omitida."""
            try:
                img_bytes, ext = SavedChartTemplateService._render_template(
                    db,
                    template=template,
                    job_ids=job_ids,
                    fmt=fmt,
                    job_display_overrides=overrides_int,
                )
            except ValueError as e:
                logger.warning("Skip plantilla %s durante reporte: %s", template.id, e)
                manifest_lines.append(
                    f"{depth_prefix}{idx:02d}. [OMITIDA] {template.name} — {e}"
                )
                return None

            base = _slugify(template.name)
            dedup_key = f"{folder}/{base}" if folder else base
            count = used_names.get(dedup_key, 0) + 1
            used_names[dedup_key] = count
            suffix = f"_{count}" if count > 1 else ""
            filename = f"{idx:02d}_{base}{suffix}.{ext}"
            arcname = f"{folder}/{filename}" if folder else filename
            zf.writestr(arcname, img_bytes)
            manifest_lines.append(
                f"{depth_prefix}{idx:02d}. {template.name}  →  {arcname}  "
                f"(tipo={template.tipo}, un={template.un}, "
                f"jobs={','.join(str(j) for j in job_ids)})"
            )
            return arcname

        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            if structured:
                assert categories is not None
                for c_idx, cat in enumerate(categories, start=1):
                    cat_slug = _slugify(cat.label)
                    cat_folder = f"{c_idx:02d}_{cat_slug}"
                    manifest_lines.append(f"[{c_idx:02d}] {cat.label}/")
                    # Ítems directos de la categoría
                    for i_idx, item in enumerate(cat.items, start=1):
                        tpl, jobs = rendered_by_template[item.template_id]
                        _write_one(
                            zf,
                            idx=i_idx,
                            template=tpl,
                            job_ids=jobs,
                            folder=cat_folder,
                            depth_prefix="  ",
                        )
                    # Subcategorías
                    for s_idx, sub in enumerate(cat.subcategories, start=1):
                        sub_slug = _slugify(sub.label)
                        sub_folder = f"{cat_folder}/{s_idx:02d}_{sub_slug}"
                        manifest_lines.append(
                            f"  [{s_idx:02d}] {sub.label}/"
                        )
                        for i_idx, item in enumerate(sub.items, start=1):
                            tpl, jobs = rendered_by_template[item.template_id]
                            _write_one(
                                zf,
                                idx=i_idx,
                                template=tpl,
                                job_ids=jobs,
                                folder=sub_folder,
                                depth_prefix="    ",
                            )
            else:
                for idx, item in enumerate(items, start=1):
                    tpl, jobs = rendered_by_template[item.template_id]
                    _write_one(
                        zf,
                        idx=idx,
                        template=tpl,
                        job_ids=jobs,
                        folder="",
                        depth_prefix="",
                    )

            zf.writestr("README.txt", "\n".join(manifest_lines))

        buffer.seek(0)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"Reporte_OSeMOSYS_{ts}.zip"
        return buffer, filename


def _report_to_public_dict(
    obj: ReportTemplate,
    *,
    current_user_id: uuid.UUID,
    owner_username: str | None,
    is_favorite: bool = False,
) -> dict:
    return {
        "id": obj.id,
        "name": obj.name,
        "description": obj.description,
        "fmt": obj.fmt,
        "items": list(obj.items or []),
        "created_at": obj.created_at,
        "updated_at": obj.updated_at,
        "is_public": bool(getattr(obj, "is_public", False)),
        "is_official": bool(getattr(obj, "is_official", False)),
        "owner_username": owner_username,
        "is_owner": obj.user_id == current_user_id,
        "layout": getattr(obj, "layout", None),
        "is_favorite": bool(is_favorite),
    }


class ReportTemplateService:
    """CRUD de reportes guardados (colecciones ordenadas de chart-templates).

    Visibilidad:
      - Dueño: acceso total (ver, editar, eliminar).
      - ``is_public=True``: otros usuarios autenticados pueden verlo y
        cargarlo en su generador (no editarlo).
      - ``is_official=True``: reporte curado, visible a todos; solo editable
        por usuarios con ``can_manage_catalogs``. Al marcarse oficial, fuerza
        ``is_public=True``.
    """

    @staticmethod
    def _promote_items_to_public(
        db: Session, *, item_ids: list[int]
    ) -> int:
        """Marca como públicas todas las plantillas indicadas (idempotente).

        Devuelve el número de filas promovidas. Se usa al marcar un reporte
        como oficial: así cualquier usuario que cargue el reporte puede ver
        las gráficas referenciadas aunque el dueño las tuviera privadas.
        """
        if not item_ids:
            return 0
        rows = (
            db.query(SavedChartTemplate)
            .filter(
                SavedChartTemplate.id.in_(item_ids),
                SavedChartTemplate.is_public.is_(False),
            )
            .all()
        )
        for r in rows:
            r.is_public = True
        return len(rows)

    @staticmethod
    def _normalize_items(
        db: Session, *, user_id: uuid.UUID, items: list[int]
    ) -> list[int]:
        """Valida que las plantillas existan y sean accesibles (propias o públicas)."""
        cleaned = [int(x) for x in items]
        if not cleaned:
            raise ValueError("El reporte debe tener al menos una gráfica.")
        seen: set[int] = set()
        ordered: list[int] = []
        for tid in cleaned:
            if tid in seen:
                continue
            seen.add(tid)
            ordered.append(tid)
        rows = db.execute(
            select(SavedChartTemplate).where(
                SavedChartTemplate.id.in_(ordered),
                or_(
                    SavedChartTemplate.user_id == user_id,
                    SavedChartTemplate.is_public.is_(True),
                ),
            )
        ).scalars().all()
        existing = {int(r.id) for r in rows}
        missing = [tid for tid in ordered if tid not in existing]
        if missing:
            raise NotFoundError(
                f"Plantillas no encontradas o sin acceso: {missing}"
            )
        return ordered

    @staticmethod
    def list_accessible(
        db: Session,
        *,
        current_user: User,
        include_others_private: bool = False,
    ) -> list[dict]:
        """Lista reportes accesibles con orden: oficiales → favoritos → resto.

        Si ``include_others_private=True`` y el usuario tiene ``is_admin_reports``
        (o ``is_admin`` como superconjunto), también se incluyen reportes
        privados de otros usuarios (solo lectura).
        """
        user_id = current_user.id
        is_admin_reports = bool(
            getattr(current_user, "is_admin_reports", False)
            or getattr(current_user, "can_manage_scenarios", False)
        )
        fav_ids = _load_report_favorite_ids(db, user_id=user_id)

        visibility_clause = or_(
            ReportTemplate.user_id == user_id,
            ReportTemplate.is_public.is_(True),
            ReportTemplate.is_official.is_(True),
        )
        # Admin reports con opt-in: amplía para cubrir privados ajenos.
        if include_others_private and is_admin_reports:
            visibility_clause = None  # ver todos los reportes

        stmt = (
            select(ReportTemplate, User.username)
            .join(User, User.id == ReportTemplate.user_id)
        )
        if visibility_clause is not None:
            stmt = stmt.where(visibility_clause)
        stmt = stmt.order_by(
            ReportTemplate.is_official.desc(),
            (ReportTemplate.user_id == user_id).desc(),
            ReportTemplate.updated_at.desc(),
        )
        rows = db.execute(stmt).all()
        out = [
            _report_to_public_dict(
                obj,
                current_user_id=user_id,
                owner_username=username,
                is_favorite=int(obj.id) in fav_ids,
            )
            for obj, username in rows
        ]
        # Orden final: oficiales primero, luego favoritos, luego el resto
        # (stable: mantiene el orden previo dentro de cada grupo).
        def _rank(d: dict) -> int:
            if d.get("is_official"):
                return 0
            if d.get("is_favorite"):
                return 1
            return 2

        out.sort(key=_rank)
        return out

    @staticmethod
    def get_accessible(
        db: Session,
        *,
        current_user: User,
        report_id: int,
    ) -> tuple[ReportTemplate, str | None]:
        row = db.execute(
            select(ReportTemplate, User.username)
            .join(User, User.id == ReportTemplate.user_id)
            .where(ReportTemplate.id == report_id)
        ).one_or_none()
        if row is None:
            raise NotFoundError("Reporte no encontrado.")
        obj, username = row
        is_admin_reports = bool(
            getattr(current_user, "is_admin_reports", False)
            or getattr(current_user, "can_manage_scenarios", False)
        )
        if (
            obj.user_id != current_user.id
            and not bool(getattr(obj, "is_public", False))
            and not bool(getattr(obj, "is_official", False))
            and not is_admin_reports
        ):
            raise NotFoundError("Reporte no encontrado.")
        return obj, username

    @staticmethod
    def get_for_user(
        db: Session, *, user_id: uuid.UUID, report_id: int
    ) -> ReportTemplate:
        """Owner-only (para mutaciones que no requieren admin)."""
        obj = db.get(ReportTemplate, report_id)
        if obj is None or obj.user_id != user_id:
            raise NotFoundError("Reporte no encontrado.")
        return obj

    @staticmethod
    def _resolve_owner_username(
        db: Session, *, user_id: uuid.UUID
    ) -> str | None:
        return db.scalar(select(User.username).where(User.id == user_id))

    @staticmethod
    def _is_admin_reports(user: User) -> bool:
        return bool(
            getattr(user, "is_admin_reports", False)
            or getattr(user, "can_manage_scenarios", False)
        )

    @staticmethod
    def create(
        db: Session,
        *,
        current_user: User,
        name: str,
        description: str | None,
        fmt: str,
        items: list[int],
        is_public: bool = False,
        is_official: bool = False,
        layout: dict | None = None,
    ) -> dict:
        if is_official and not ReportTemplateService._is_admin_reports(current_user):
            raise ForbiddenError(
                "Se requiere permiso 'Admin Reportes' para marcar un reporte como oficial."
            )
        ordered = ReportTemplateService._normalize_items(
            db, user_id=current_user.id, items=items
        )
        obj = ReportTemplate(
            user_id=current_user.id,
            name=name.strip()[:255],
            description=description,
            fmt=fmt,
            items=ordered,
            is_public=bool(is_public) or bool(is_official),
            is_official=bool(is_official),
            layout=layout,
        )
        db.add(obj)
        # Si el reporte es compartido (público u oficial), promovemos las
        # plantillas referenciadas a públicas — así cualquier usuario que
        # cargue el reporte ve y usa todas las gráficas en su generador.
        if obj.is_public or obj.is_official:
            ReportTemplateService._promote_items_to_public(
                db, item_ids=ordered
            )
        db.commit()
        db.refresh(obj)
        username = ReportTemplateService._resolve_owner_username(
            db, user_id=current_user.id
        )
        return _report_to_public_dict(
            obj,
            current_user_id=current_user.id,
            owner_username=username,
            is_favorite=False,
        )

    @staticmethod
    def update(
        db: Session,
        *,
        current_user: User,
        report_id: int,
        name: str | None,
        description: str | None | object = ...,
        fmt: str | None,
        items: list[int] | None,
        is_public: bool | None = None,
        is_official: bool | None = None,
        layout: dict | None | object = ...,
    ) -> dict:
        """Actualiza el reporte con reglas de acceso granulares.

        Reglas:
          - Dueño: edita todo excepto ``is_official`` (requiere Admin Reportes).
          - Admin Reportes (no dueño):
            * Reportes oficiales → edita todo.
            * Reportes públicos no oficiales → puede renombrar + toggle oficial.
            * Reportes privados → lectura (no edita).
          - Otros usuarios: no pueden editar reportes que no son suyos.
        """
        is_admin_reports = ReportTemplateService._is_admin_reports(current_user)
        obj = db.get(ReportTemplate, report_id)
        if obj is None:
            raise NotFoundError("Reporte no encontrado.")

        is_owner = obj.user_id == current_user.id
        is_official_current = bool(getattr(obj, "is_official", False))
        is_public_current = bool(getattr(obj, "is_public", False))

        if not is_owner and not is_admin_reports:
            raise NotFoundError("Reporte no encontrado.")

        # Ámbito de mutaciones permitidas según combinación de rol + visibilidad.
        full_edit = is_owner or (is_admin_reports and is_official_current)
        rename_and_official_only = (
            is_admin_reports
            and not is_owner
            and is_public_current
            and not is_official_current
        )

        # Cambiar is_official requiere Admin Reportes.
        if is_official is not None and not is_admin_reports:
            raise ForbiddenError(
                "Solo Admin Reportes puede cambiar el estado 'oficial'."
            )

        # Si NO se tiene edit full, validar que solo vengan cambios permitidos.
        if not full_edit:
            if not rename_and_official_only:
                raise ForbiddenError(
                    "No tienes permiso para editar este reporte."
                )
            # En modo rename/official-only, permitir solo `name` e `is_official`.
            disallowed = [
                (description is not ..., "description"),
                (fmt is not None, "fmt"),
                (items is not None, "items"),
                (is_public is not None, "is_public"),
                (layout is not ..., "layout"),
            ]
            bad = [n for (flag, n) in disallowed if flag]
            if bad:
                raise ForbiddenError(
                    "En reportes públicos ajenos solo puedes cambiar 'name' "
                    "y 'is_official'. Campos no permitidos: " + ", ".join(bad)
                )

        if name is not None:
            obj.name = name.strip()[:255]
        if description is not ...:
            obj.description = description
        if fmt is not None:
            obj.fmt = fmt
        if items is not None:
            obj.items = ReportTemplateService._normalize_items(
                db, user_id=obj.user_id, items=items
            )
        if is_public is not None:
            obj.is_public = bool(is_public)
        if is_official is not None:
            obj.is_official = bool(is_official)
            if obj.is_official:
                obj.is_public = True  # un oficial siempre es público
        if layout is not ...:
            obj.layout = layout
        # Si el reporte quedó compartido (público u oficial), promovemos sus
        # plantillas a públicas.
        if obj.is_public or obj.is_official:
            ReportTemplateService._promote_items_to_public(
                db, item_ids=list(obj.items or [])
            )
        db.commit()
        db.refresh(obj)
        username = ReportTemplateService._resolve_owner_username(
            db, user_id=obj.user_id
        )
        fav = db.execute(
            select(ReportTemplateFavorite).where(
                ReportTemplateFavorite.user_id == current_user.id,
                ReportTemplateFavorite.report_id == obj.id,
            )
        ).scalar_one_or_none()
        return _report_to_public_dict(
            obj,
            current_user_id=current_user.id,
            owner_username=username,
            is_favorite=fav is not None,
        )

    @staticmethod
    def delete(
        db: Session, *, current_user: User, report_id: int
    ) -> None:
        """Borra el reporte. Dueño puede borrar el suyo; Admin Reportes puede
        borrar oficiales. No puede borrar reportes públicos no oficiales ajenos
        ni privados ajenos.
        """
        is_admin_reports = ReportTemplateService._is_admin_reports(current_user)
        obj = db.get(ReportTemplate, report_id)
        if obj is None:
            raise NotFoundError("Reporte no encontrado.")
        is_owner = obj.user_id == current_user.id
        is_official = bool(getattr(obj, "is_official", False))
        if not is_owner and not (is_admin_reports and is_official):
            raise ForbiddenError("No tienes permiso para borrar este reporte.")
        db.delete(obj)
        db.commit()

    # ---------------- Favoritos ----------------

    @staticmethod
    def set_favorite(
        db: Session,
        *,
        current_user: User,
        report_id: int,
        is_favorite: bool,
    ) -> dict:
        obj, username = ReportTemplateService.get_accessible(
            db, current_user=current_user, report_id=report_id
        )
        existing = db.execute(
            select(ReportTemplateFavorite).where(
                ReportTemplateFavorite.user_id == current_user.id,
                ReportTemplateFavorite.report_id == report_id,
            )
        ).scalar_one_or_none()
        if is_favorite and existing is None:
            db.add(
                ReportTemplateFavorite(
                    user_id=current_user.id, report_id=report_id,
                )
            )
            db.commit()
        elif not is_favorite and existing is not None:
            db.delete(existing)
            db.commit()
        return _report_to_public_dict(
            obj,
            current_user_id=current_user.id,
            owner_username=username,
            is_favorite=bool(is_favorite),
        )

    # ---------------- Copy ----------------

    @staticmethod
    def copy_report(
        db: Session,
        *,
        current_user: User,
        report_id: int,
        new_name: str | None = None,
    ) -> dict:
        """Crea una copia del reporte para el usuario actual.

        Para las plantillas de gráfica referenciadas:
          - Si la plantilla es accesible (propia o pública), se reutiliza.
          - Si NO es accesible (privada ajena — solo visible porque el caller
            es Admin Reportes mirando reportes privados), se clona una copia
            privada para el usuario y se referencia esa.
        La copia del reporte nace como PRIVADA y no oficial, dueño = caller.
        El layout se clona tal cual, reemplazando referencias a IDs clonados.
        """
        src, _ = ReportTemplateService.get_accessible(
            db, current_user=current_user, report_id=report_id
        )
        original_ids = list(src.items or [])

        # Resolver accesibilidad de cada plantilla.
        accessible_rows = db.execute(
            select(SavedChartTemplate).where(
                SavedChartTemplate.id.in_(original_ids),
                or_(
                    SavedChartTemplate.user_id == current_user.id,
                    SavedChartTemplate.is_public.is_(True),
                ),
            )
        ).scalars().all()
        accessible_set = {int(r.id) for r in accessible_rows}

        # Mapa oldId -> nuevoId (solo para los clonados).
        id_map: dict[int, int] = {}
        # Clonar las que no son accesibles.
        inaccessible_ids = [i for i in original_ids if i not in accessible_set]
        if inaccessible_ids:
            originals = db.execute(
                select(SavedChartTemplate).where(
                    SavedChartTemplate.id.in_(inaccessible_ids),
                )
            ).scalars().all()
            for orig in originals:
                clone = SavedChartTemplate(
                    user_id=current_user.id,
                    name=orig.name,
                    description=orig.description,
                    tipo=orig.tipo,
                    un=orig.un,
                    sub_filtro=orig.sub_filtro,
                    loc=orig.loc,
                    variable=orig.variable,
                    agrupar_por=orig.agrupar_por,
                    view_mode=orig.view_mode,
                    compare_mode=orig.compare_mode,
                    bar_orientation=orig.bar_orientation,
                    facet_placement=orig.facet_placement,
                    facet_legend_mode=orig.facet_legend_mode,
                    num_scenarios=orig.num_scenarios,
                    legend_title=orig.legend_title,
                    filename_mode=orig.filename_mode,
                    is_public=False,  # privadas en la copia
                )
                db.add(clone)
                db.flush()
                id_map[int(orig.id)] = int(clone.id)

        # Construir la nueva lista de items.
        new_items = [id_map.get(i, i) for i in original_ids]

        # Reescribir el layout reemplazando las referencias a ids antiguos.
        def _remap_layout(layout: dict | None) -> dict | None:
            if not isinstance(layout, dict):
                return layout
            cats = layout.get("categories") or []
            new_cats = []
            for c in cats:
                new_c = {
                    **c,
                    "items": [id_map.get(int(i), int(i)) for i in c.get("items", [])],
                    "subcategories": [
                        {
                            **s,
                            "items": [
                                id_map.get(int(i), int(i)) for i in s.get("items", [])
                            ],
                        }
                        for s in c.get("subcategories", [])
                    ],
                }
                new_cats.append(new_c)
            return {**layout, "categories": new_cats}

        copy_name = (new_name or f"{src.name} (copia)").strip()[:255]
        copy = ReportTemplate(
            user_id=current_user.id,
            name=copy_name,
            description=src.description,
            fmt=src.fmt,
            items=new_items,
            is_public=False,
            is_official=False,
            layout=_remap_layout(src.layout),
        )
        db.add(copy)
        db.commit()
        db.refresh(copy)
        username = ReportTemplateService._resolve_owner_username(
            db, user_id=current_user.id
        )
        return _report_to_public_dict(
            copy,
            current_user_id=current_user.id,
            owner_username=username,
            is_favorite=False,
        )
