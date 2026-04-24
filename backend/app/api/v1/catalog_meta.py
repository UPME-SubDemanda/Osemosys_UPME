"""Endpoints de administración del catálogo de visualización (Fase 3).

Fase 3.2: invalidación de cache.
Fase 3.3.A: CRUD de colores (``catalog_meta_color_palette``).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_catalog_manager
from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import get_db
from app.models import User
from app.schemas.catalog_meta import (
    ALLOWED_COLOR_GROUPS,
    AuditListResponse,
    ChartModuleCreate,
    ChartModulePublic,
    ChartModulesTreeResponse,
    ChartModuleUpdate,
    ChartSubmoduleCreate,
    ChartSubmodulePublic,
    ChartSubmoduleUpdate,
    ColorItemCreate,
    ColorItemPublic,
    ColorItemUpdate,
    ColorListResponse,
    LabelItemCreate,
    LabelItemPublic,
    LabelItemUpdate,
    LabelListResponse,
    SectorMappingCreate,
    SectorMappingListResponse,
    SectorMappingPublic,
    SectorMappingUpdate,
    TechFamilyBulkAdd,
    TechFamilyItemCreate,
    TechFamilyItemPublic,
    TechFamilyItemUpdate,
    TechFamilyListResponse,
    ChartConfigCreate,
    ChartConfigListResponse,
    ChartConfigPublic,
    ChartConfigUpdate,
    ChartSubfilterCreate,
    ChartSubfilterPublic,
    ChartSubfilterUpdate,
    VariableUnitCreate,
    VariableUnitListResponse,
    VariableUnitPublic,
    VariableUnitUpdate,
)
from app.services.catalog_meta_service import (
    CatalogMetaAuditService,
    CatalogMetaChartConfigService,
    CatalogMetaColorService,
    CatalogMetaLabelService,
    CatalogMetaModuleService,
    CatalogMetaSectorService,
    CatalogMetaTechFamilyService,
    CatalogMetaVariableUnitService,
)
from app.visualization.catalog_reader import bump_version, get_chart_catalog_meta

router = APIRouter(prefix="/catalog-meta", tags=["catalog-meta"])


@router.post("/invalidate-cache")
def invalidate_cache(_: User = Depends(get_catalog_manager)) -> dict[str, str]:
    """Fuerza a todos los workers a recargar los dicts (colors, labels, etc)."""
    bump_version()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
#  Colores (3.3.A)
# ---------------------------------------------------------------------------

def _to_public(row) -> dict:
    return {
        "id": row.id,
        "key": row.key,
        "group": row.group,
        "color_hex": row.color_hex,
        "description": row.description,
        "sort_order": row.sort_order,
        "updated_at": row.updated_at,
    }


@router.get("/colors", response_model=ColorListResponse)
def list_colors(
    group: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_catalog_manager),
) -> dict:
    if group and group not in ALLOWED_COLOR_GROUPS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"group inválido; permitidos: {ALLOWED_COLOR_GROUPS}",
        )
    items = [_to_public(r) for r in CatalogMetaColorService.list(db, group=group)]
    return {
        "items": items,
        "total": len(items),
        "allowed_groups": list(ALLOWED_COLOR_GROUPS),
    }


@router.post("/colors", response_model=ColorItemPublic, status_code=201)
def create_color(
    payload: ColorItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict:
    try:
        row = CatalogMetaColorService.create(
            db,
            user=current_user,
            key=payload.key,
            group=payload.group,
            color_hex=payload.color_hex,
            description=payload.description,
            sort_order=payload.sort_order,
        )
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    return _to_public(row)


@router.patch("/colors/{color_id}", response_model=ColorItemPublic)
def update_color(
    color_id: int,
    payload: ColorItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict:
    data = payload.model_dump(exclude_unset=True)
    try:
        row = CatalogMetaColorService.update(
            db,
            user=current_user,
            color_id=color_id,
            color_hex=data.get("color_hex"),
            description=data["description"] if "description" in data else ...,
            sort_order=data.get("sort_order"),
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _to_public(row)


@router.delete("/colors/{color_id}", status_code=204)
def delete_color(
    color_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> None:
    try:
        CatalogMetaColorService.delete(db, user=current_user, color_id=color_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ---------------------------------------------------------------------------
#  Labels (3.3.B)
# ---------------------------------------------------------------------------

def _label_to_public(row) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "label_es": row.label_es,
        "label_en": row.label_en,
        "category": row.category,
        "sort_order": row.sort_order,
        "updated_at": row.updated_at,
    }


@router.get("/labels", response_model=LabelListResponse)
def list_labels(
    search: str | None = None,
    category: str | None = None,
    offset: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(get_catalog_manager),
) -> dict:
    items, total = CatalogMetaLabelService.list(
        db, search=search, category=category, offset=offset, limit=limit
    )
    categories = CatalogMetaLabelService.list_categories(db)
    return {
        "items": [_label_to_public(r) for r in items],
        "total": int(total),
        "offset": max(0, offset),
        "limit": max(1, min(limit, 500)),
        "categories": categories,
    }


@router.post("/labels", response_model=LabelItemPublic, status_code=201)
def create_label(
    payload: LabelItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict:
    try:
        row = CatalogMetaLabelService.create(
            db,
            user=current_user,
            code=payload.code,
            label_es=payload.label_es,
            label_en=payload.label_en,
            category=payload.category,
            sort_order=payload.sort_order,
        )
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    return _label_to_public(row)


@router.patch("/labels/{label_id}", response_model=LabelItemPublic)
def update_label(
    label_id: int,
    payload: LabelItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict:
    data = payload.model_dump(exclude_unset=True)
    try:
        row = CatalogMetaLabelService.update(
            db,
            user=current_user,
            label_id=label_id,
            label_es=data.get("label_es"),
            label_en=data["label_en"] if "label_en" in data else ...,
            category=data["category"] if "category" in data else ...,
            sort_order=data.get("sort_order"),
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _label_to_public(row)


@router.delete("/labels/{label_id}", status_code=204)
def delete_label(
    label_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> None:
    try:
        CatalogMetaLabelService.delete(db, user=current_user, label_id=label_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ---------------------------------------------------------------------------
#  Audit / Historial
# ---------------------------------------------------------------------------

@router.get("/audit", response_model=AuditListResponse)
def list_audit(
    table_name: str | None = None,
    action: str | None = None,
    row_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(get_catalog_manager),
) -> dict:
    """Historial de cambios sobre todo el catálogo editable.

    Filtros opcionales: ``table_name`` (por tabla), ``action``
    (INSERT/UPDATE/DELETE) y ``row_id`` (todos los cambios de una fila
    específica — útil para mostrar historial de un color en particular).
    """
    items, total, tables = CatalogMetaAuditService.list(
        db,
        table_name=table_name,
        action=action,
        row_id=row_id,
        offset=offset,
        limit=limit,
    )
    return {
        "items": items,
        "total": int(total),
        "offset": max(0, offset),
        "limit": max(1, min(limit, 500)),
        "tables": tables,
    }


# ---------------------------------------------------------------------------
#  Sector mapping (3.3.C)
# ---------------------------------------------------------------------------

def _sector_to_public(row) -> dict:
    return {
        "id": row.id,
        "tech_prefix": row.tech_prefix,
        "sector_name": row.sector_name,
        "sort_order": row.sort_order,
        "updated_at": row.updated_at,
    }


@router.get("/sectors", response_model=SectorMappingListResponse)
def list_sectors(
    db: Session = Depends(get_db),
    _: User = Depends(get_catalog_manager),
) -> dict:
    items = [_sector_to_public(r) for r in CatalogMetaSectorService.list(db)]
    return {"items": items, "total": len(items)}


@router.post("/sectors", response_model=SectorMappingPublic, status_code=201)
def create_sector(
    payload: SectorMappingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict:
    try:
        row = CatalogMetaSectorService.create(
            db,
            user=current_user,
            tech_prefix=payload.tech_prefix,
            sector_name=payload.sector_name,
            sort_order=payload.sort_order,
        )
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    return _sector_to_public(row)


@router.patch("/sectors/{row_id}", response_model=SectorMappingPublic)
def update_sector(
    row_id: int,
    payload: SectorMappingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict:
    data = payload.model_dump(exclude_unset=True)
    try:
        row = CatalogMetaSectorService.update(
            db,
            user=current_user,
            row_id=row_id,
            sector_name=data.get("sector_name"),
            sort_order=data.get("sort_order"),
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _sector_to_public(row)


@router.delete("/sectors/{row_id}", status_code=204)
def delete_sector(
    row_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> None:
    try:
        CatalogMetaSectorService.delete(db, user=current_user, row_id=row_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ---------------------------------------------------------------------------
#  Tech families (3.3.C)
# ---------------------------------------------------------------------------

def _family_to_public(row) -> dict:
    return {
        "id": row.id,
        "family_code": row.family_code,
        "tech_prefix": row.tech_prefix,
        "sort_order": row.sort_order,
        "updated_at": row.updated_at,
    }


@router.get("/tech-families", response_model=TechFamilyListResponse)
def list_tech_families(
    family_code: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_catalog_manager),
) -> dict:
    items, families = CatalogMetaTechFamilyService.list(db, family_code=family_code)
    return {
        "items": [_family_to_public(r) for r in items],
        "total": len(items),
        "families": families,
    }


@router.post("/tech-families", response_model=TechFamilyItemPublic, status_code=201)
def create_tech_family(
    payload: TechFamilyItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict:
    try:
        row = CatalogMetaTechFamilyService.create(
            db,
            user=current_user,
            family_code=payload.family_code,
            tech_prefix=payload.tech_prefix,
            sort_order=payload.sort_order,
        )
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    return _family_to_public(row)


@router.post("/tech-families/bulk", response_model=list[TechFamilyItemPublic])
def bulk_add_tech_family(
    payload: TechFamilyBulkAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> list[dict]:
    """Agrega N prefijos a una familia (ignora duplicados)."""
    added = CatalogMetaTechFamilyService.bulk_add(
        db,
        user=current_user,
        family_code=payload.family_code,
        tech_prefixes=payload.tech_prefixes,
    )
    return [_family_to_public(r) for r in added]


@router.patch("/tech-families/{row_id}", response_model=TechFamilyItemPublic)
def update_tech_family(
    row_id: int,
    payload: TechFamilyItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict:
    data = payload.model_dump(exclude_unset=True)
    try:
        row = CatalogMetaTechFamilyService.update(
            db,
            user=current_user,
            row_id=row_id,
            sort_order=data.get("sort_order"),
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _family_to_public(row)


@router.delete("/tech-families/{row_id}", status_code=204)
def delete_tech_family(
    row_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> None:
    try:
        CatalogMetaTechFamilyService.delete(db, user=current_user, row_id=row_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ---------------------------------------------------------------------------
#  Code usage — warning de propagación al editar label/color
# ---------------------------------------------------------------------------

@router.get("/usage")
def code_usage(
    codes: str,  # CSV de códigos
    _: User = Depends(get_catalog_manager),
) -> dict:
    """Para cada código devuelve cuántas gráficas del catálogo lo contienen.

    Heurística: se considera que un código pertenece a una gráfica si empieza
    por alguno de los ``technology_prefixes`` o ``fuel_prefixes`` declarados
    en su ``data_explorer_filters``. Gráficas sin prefijos (catch-all) no se
    cuentan aquí para evitar inflar el conteo con "Todos".
    """
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    if not code_list:
        return {"items": {}}

    meta = get_chart_catalog_meta()
    out: dict[str, dict] = {}
    for code in code_list:
        matched_tipos: list[str] = []
        matched_labels: list[str] = []
        for tipo, m in meta.items():
            de = m.get("data_explorer_filters") or {}
            tech_pref = (de or {}).get("technology_prefixes") or []
            fuel_pref = (de or {}).get("fuel_prefixes") or []
            emis_names = (de or {}).get("emission_names") or []
            if tech_pref and any(code.startswith(p) for p in tech_pref):
                matched_tipos.append(tipo)
                matched_labels.append(m.get("label_titulo") or tipo)
                continue
            if fuel_pref and any(code.startswith(p) for p in fuel_pref):
                matched_tipos.append(tipo)
                matched_labels.append(m.get("label_titulo") or tipo)
                continue
            if emis_names and code in emis_names:
                matched_tipos.append(tipo)
                matched_labels.append(m.get("label_titulo") or tipo)
        out[code] = {
            "count": len(matched_tipos),
            "chart_tipos": matched_tipos[:50],
            "chart_labels": matched_labels[:50],
        }
    return {"items": out}


# ---------------------------------------------------------------------------
#  Upsert endpoints — editor rápido desde la gráfica
# ---------------------------------------------------------------------------

@router.post("/labels/upsert", response_model=LabelItemPublic)
def upsert_label(
    payload: LabelItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict:
    """Crea o actualiza un label keyed by ``code`` — no falla si ya existe."""
    from app.models import CatalogMetaLabel
    from sqlalchemy import select as _select

    row = db.execute(
        _select(CatalogMetaLabel).where(CatalogMetaLabel.code == payload.code)
    ).scalar_one_or_none()
    if row is None:
        try:
            row = CatalogMetaLabelService.create(
                db,
                user=current_user,
                code=payload.code,
                label_es=payload.label_es,
                label_en=payload.label_en,
                category=payload.category,
                sort_order=payload.sort_order,
            )
        except ConflictError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    else:
        row = CatalogMetaLabelService.update(
            db,
            user=current_user,
            label_id=row.id,
            label_es=payload.label_es,
            label_en=payload.label_en,
            category=payload.category,
            sort_order=payload.sort_order,
        )
    return _label_to_public(row)


@router.post("/colors/upsert", response_model=ColorItemPublic)
def upsert_color(
    payload: ColorItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict:
    """Crea o actualiza un color keyed by ``(group, key)``."""
    from app.models import CatalogMetaColorPalette
    from sqlalchemy import select as _select

    row = db.execute(
        _select(CatalogMetaColorPalette).where(
            CatalogMetaColorPalette.group == payload.group,
            CatalogMetaColorPalette.key == payload.key,
        )
    ).scalar_one_or_none()
    if row is None:
        try:
            row = CatalogMetaColorService.create(
                db,
                user=current_user,
                key=payload.key,
                group=payload.group,
                color_hex=payload.color_hex,
                description=payload.description,
                sort_order=payload.sort_order,
            )
        except ConflictError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    else:
        row = CatalogMetaColorService.update(
            db,
            user=current_user,
            color_id=row.id,
            color_hex=payload.color_hex,
            description=payload.description,
            sort_order=payload.sort_order,
        )
    return _to_public(row)


# ---------------------------------------------------------------------------
#  Modules + Submodules (3.3.D)
# ---------------------------------------------------------------------------

@router.get("/modules", response_model=ChartModulesTreeResponse)
def list_modules(
    db: Session = Depends(get_db),
    _: User = Depends(get_catalog_manager),
) -> dict:
    return {"items": CatalogMetaModuleService.tree(db)}


@router.post("/modules", response_model=ChartModulePublic, status_code=201)
def create_module(
    payload: ChartModuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict:
    try:
        row = CatalogMetaModuleService.create_module(
            db,
            user=current_user,
            code=payload.code,
            label=payload.label,
            icon=payload.icon,
            sort_order=payload.sort_order,
            is_visible=payload.is_visible,
        )
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    return {
        "id": row.id,
        "code": row.code,
        "label": row.label,
        "icon": row.icon,
        "sort_order": row.sort_order,
        "is_visible": bool(row.is_visible),
        "updated_at": row.updated_at,
        "submodules": [],
        "chart_count": 0,
    }


@router.patch("/modules/{row_id}", response_model=ChartModulePublic)
def update_module(
    row_id: int,
    payload: ChartModuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict:
    data = payload.model_dump(exclude_unset=True)
    try:
        row = CatalogMetaModuleService.update_module(
            db,
            user=current_user,
            row_id=row_id,
            label=data.get("label"),
            icon=data["icon"] if "icon" in data else ...,
            sort_order=data.get("sort_order"),
            is_visible=data.get("is_visible"),
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {
        "id": row.id,
        "code": row.code,
        "label": row.label,
        "icon": row.icon,
        "sort_order": row.sort_order,
        "is_visible": bool(row.is_visible),
        "updated_at": row.updated_at,
        "submodules": [],
        "chart_count": 0,
    }


@router.delete("/modules/{row_id}", status_code=204)
def delete_module(
    row_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> None:
    try:
        CatalogMetaModuleService.delete_module(db, user=current_user, row_id=row_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.post("/submodules", response_model=ChartSubmodulePublic, status_code=201)
def create_submodule(
    payload: ChartSubmoduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict:
    try:
        row = CatalogMetaModuleService.create_submodule(
            db,
            user=current_user,
            module_id=payload.module_id,
            code=payload.code,
            label=payload.label,
            icon=payload.icon,
            sort_order=payload.sort_order,
            is_visible=payload.is_visible,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    return {
        "id": row.id,
        "module_id": row.module_id,
        "code": row.code,
        "label": row.label,
        "icon": row.icon,
        "sort_order": row.sort_order,
        "is_visible": bool(row.is_visible),
        "updated_at": row.updated_at,
    }


@router.patch("/submodules/{row_id}", response_model=ChartSubmodulePublic)
def update_submodule(
    row_id: int,
    payload: ChartSubmoduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict:
    data = payload.model_dump(exclude_unset=True)
    try:
        row = CatalogMetaModuleService.update_submodule(
            db,
            user=current_user,
            row_id=row_id,
            module_id=data.get("module_id"),
            label=data.get("label"),
            icon=data["icon"] if "icon" in data else ...,
            sort_order=data.get("sort_order"),
            is_visible=data.get("is_visible"),
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {
        "id": row.id,
        "module_id": row.module_id,
        "code": row.code,
        "label": row.label,
        "icon": row.icon,
        "sort_order": row.sort_order,
        "is_visible": bool(row.is_visible),
        "updated_at": row.updated_at,
    }


@router.delete("/submodules/{row_id}", status_code=204)
def delete_submodule(
    row_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> None:
    try:
        CatalogMetaModuleService.delete_submodule(db, user=current_user, row_id=row_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ---------------------------------------------------------------------------
#  Variable units (3.3.E)
# ---------------------------------------------------------------------------

def _unit_to_public(row) -> dict:
    return {
        "id": row.id,
        "variable_name": row.variable_name,
        "unit_base": row.unit_base,
        "display_units_json": row.display_units_json,
        "updated_at": row.updated_at,
    }


@router.get("/variable-units", response_model=VariableUnitListResponse)
def list_units(
    db: Session = Depends(get_db),
    _: User = Depends(get_catalog_manager),
) -> dict:
    items = [_unit_to_public(r) for r in CatalogMetaVariableUnitService.list(db)]
    return {"items": items, "total": len(items)}


@router.post("/variable-units", response_model=VariableUnitPublic, status_code=201)
def create_unit(
    payload: VariableUnitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict:
    try:
        row = CatalogMetaVariableUnitService.create(
            db,
            user=current_user,
            variable_name=payload.variable_name,
            unit_base=payload.unit_base,
            display_units_json=payload.display_units_json,
        )
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    return _unit_to_public(row)


@router.patch("/variable-units/{row_id}", response_model=VariableUnitPublic)
def update_unit(
    row_id: int,
    payload: VariableUnitUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict:
    data = payload.model_dump(exclude_unset=True)
    try:
        row = CatalogMetaVariableUnitService.update(
            db,
            user=current_user,
            row_id=row_id,
            unit_base=data.get("unit_base"),
            display_units_json=data["display_units_json"] if "display_units_json" in data else ...,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _unit_to_public(row)


@router.delete("/variable-units/{row_id}", status_code=204)
def delete_unit(
    row_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> None:
    try:
        CatalogMetaVariableUnitService.delete(db, user=current_user, row_id=row_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ---------------------------------------------------------------------------
#  Chart config + sub-filtros (3.3.F + 3.3.H)
# ---------------------------------------------------------------------------

@router.get("/charts", response_model=ChartConfigListResponse)
def list_chart_configs(
    module_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_catalog_manager),
) -> dict:
    items = CatalogMetaChartConfigService.list(db, module_id=module_id)
    return {"items": items, "total": len(items)}


@router.post("/charts", response_model=ChartConfigPublic, status_code=201)
def create_chart_config(
    payload: ChartConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict:
    try:
        return CatalogMetaChartConfigService.create(
            db, user=current_user, payload=payload.model_dump(exclude_unset=False)
        )
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.patch("/charts/{row_id}", response_model=ChartConfigPublic)
def update_chart_config(
    row_id: int,
    payload: ChartConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict:
    try:
        return CatalogMetaChartConfigService.update(
            db,
            user=current_user,
            row_id=row_id,
            patch=payload.model_dump(exclude_unset=True),
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/charts/{row_id}", status_code=204)
def delete_chart_config(
    row_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> None:
    try:
        CatalogMetaChartConfigService.delete(db, user=current_user, row_id=row_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/chart-subfilters", response_model=ChartSubfilterPublic, status_code=201)
def create_chart_subfilter(
    payload: ChartSubfilterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict:
    try:
        row = CatalogMetaChartConfigService.create_subfilter(
            db,
            user=current_user,
            chart_id=payload.chart_id,
            group_label=payload.group_label,
            code=payload.code,
            display_label=payload.display_label,
            sort_order=payload.sort_order,
            default_selected=payload.default_selected,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    return {
        "id": row.id,
        "chart_id": row.chart_id,
        "group_label": row.group_label,
        "code": row.code,
        "display_label": row.display_label,
        "sort_order": row.sort_order,
        "default_selected": bool(row.default_selected),
    }


@router.patch("/chart-subfilters/{row_id}", response_model=ChartSubfilterPublic)
def update_chart_subfilter(
    row_id: int,
    payload: ChartSubfilterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> dict:
    try:
        row = CatalogMetaChartConfigService.update_subfilter(
            db,
            user=current_user,
            row_id=row_id,
            patch=payload.model_dump(exclude_unset=True),
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {
        "id": row.id,
        "chart_id": row.chart_id,
        "group_label": row.group_label,
        "code": row.code,
        "display_label": row.display_label,
        "sort_order": row.sort_order,
        "default_selected": bool(row.default_selected),
    }


@router.delete("/chart-subfilters/{row_id}", status_code=204)
def delete_chart_subfilter(
    row_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_catalog_manager),
) -> None:
    try:
        CatalogMetaChartConfigService.delete_subfilter(db, user=current_user, row_id=row_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
