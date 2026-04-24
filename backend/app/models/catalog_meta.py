"""Modelos ORM del catálogo editable de visualización (Fase 3).

Reemplaza los dicts hardcodeados en ``app/visualization/{configs,
configs_comparacion, colors, labels}.py`` y ``frontend/.../ChartSelector.tsx``.
Todas las tablas viven en el schema ``osemosys`` y usan prefijo
``catalog_meta_*``. Auditoría por fila en ``created_at``, ``updated_at``,
``modified_by``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "osemosys"


def _audit(prefix: str) -> dict:
    """Helper unused — each model declares its own auditing columns explicitly."""
    return {}


class CatalogMetaColorPalette(Base):
    """Paleta unificada de colores (fuel, sector, emission, pwr, family)."""

    __tablename__ = "catalog_meta_color_palette"
    __table_args__ = (
        UniqueConstraint("group", "key", name="uq_color_palette_group_key"),
        Index("ix_color_palette_group", "group"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    color_hex: Mapped[str] = mapped_column(String(9), nullable=False)
    group: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    modified_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True)


class CatalogMetaLabel(Base):
    """Código → nombre display (reemplaza DISPLAY_NAMES + NOMBRES_COMBUSTIBLES)."""

    __tablename__ = "catalog_meta_label"
    __table_args__ = (
        UniqueConstraint("code", name="uq_label_code"),
        Index("ix_label_category", "category"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    label_es: Mapped[str] = mapped_column(String(255), nullable=False)
    label_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    modified_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True)


class CatalogMetaSectorMapping(Base):
    """Prefijo tecnológico → sector (reemplaza MAPA_SECTOR)."""

    __tablename__ = "catalog_meta_sector_mapping"
    __table_args__ = (
        UniqueConstraint("tech_prefix", name="uq_sector_mapping_prefix"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tech_prefix: Mapped[str] = mapped_column(String(64), nullable=False)
    sector_name: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    modified_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True)


class CatalogMetaTechFamily(Base):
    """Familia tech → prefijos (reemplaza FAMILIAS_TEC)."""

    __tablename__ = "catalog_meta_tech_family"
    __table_args__ = (
        UniqueConstraint("family_code", "tech_prefix", name="uq_tech_family_row"),
        Index("ix_tech_family_family", "family_code"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_code: Mapped[str] = mapped_column(String(64), nullable=False)
    tech_prefix: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    modified_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True)


class CatalogMetaChartModule(Base):
    """Módulos del ChartSelector (nivel 1)."""

    __tablename__ = "catalog_meta_chart_module"
    __table_args__ = (
        UniqueConstraint("code", name="uq_chart_module_code"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    modified_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True)


class CatalogMetaChartSubmodule(Base):
    """Submódulos bajo un módulo (nivel 2)."""

    __tablename__ = "catalog_meta_chart_submodule"
    __table_args__ = (
        UniqueConstraint("module_id", "code", name="uq_chart_submodule_code"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("osemosys.catalog_meta_chart_module.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    modified_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True)


class CatalogMetaChartConfig(Base):
    """Configuración completa de una gráfica (reemplaza CONFIGS)."""

    __tablename__ = "catalog_meta_chart_config"
    __table_args__ = (
        UniqueConstraint("tipo", name="uq_chart_config_tipo"),
        Index("ix_chart_config_module", "module_id"),
        Index("ix_chart_config_submodule", "submodule_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo: Mapped[str] = mapped_column(String(64), nullable=False)

    module_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("osemosys.catalog_meta_chart_module.id", ondelete="RESTRICT"),
        nullable=False,
    )
    submodule_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("osemosys.catalog_meta_chart_submodule.id", ondelete="SET NULL"),
        nullable=True,
    )

    label_titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    label_figura: Mapped[str | None] = mapped_column(String(64), nullable=True)
    variable_default: Mapped[str] = mapped_column(String(128), nullable=False)

    filtro_kind: Mapped[str] = mapped_column(String(64), nullable=False, default="prefix", server_default="prefix")
    filtro_params_json: Mapped[object | None] = mapped_column(JSONB, nullable=True)

    agrupar_por_default: Mapped[str] = mapped_column(String(32), nullable=False, default="TECNOLOGIA", server_default="TECNOLOGIA")
    agrupaciones_permitidas_json: Mapped[object | None] = mapped_column(JSONB, nullable=True)

    color_fn_key: Mapped[str] = mapped_column(String(32), nullable=False, default="tecnologias", server_default="tecnologias")

    flags_json: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    msg_sin_datos: Mapped[str | None] = mapped_column(String(512), nullable=True)

    data_explorer_filters_json: Mapped[object | None] = mapped_column(JSONB, nullable=True)

    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    modified_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True)


class CatalogMetaChartSubfilter(Base):
    """Sub-filtros editables de una gráfica (CARRETERA, AVI, CKN, ...)."""

    __tablename__ = "catalog_meta_chart_subfilter"
    __table_args__ = (
        UniqueConstraint("chart_id", "code", name="uq_chart_subfilter_code"),
        Index("ix_chart_subfilter_chart", "chart_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chart_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("osemosys.catalog_meta_chart_config.id", ondelete="CASCADE"),
        nullable=False,
    )
    group_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    display_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    default_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    modified_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True)


class CatalogMetaChartSubfilterGroup(Base):
    """Agrupación combinable de sub-filtros (``Transporte liviano`` = [LDV, TAX, ...])."""

    __tablename__ = "catalog_meta_chart_subfilter_group"
    __table_args__ = ({"schema": SCHEMA},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chart_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("osemosys.catalog_meta_chart_config.id", ondelete="CASCADE"),
        nullable=False,
    )
    group_label: Mapped[str] = mapped_column(String(128), nullable=False)
    subfilter_codes_json: Mapped[object] = mapped_column(JSONB, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    modified_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True)


class CatalogMetaVariableUnit(Base):
    """Unidad base + conversiones display por variable."""

    __tablename__ = "catalog_meta_variable_unit"
    __table_args__ = (
        UniqueConstraint("variable_name", name="uq_variable_unit_name"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    variable_name: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_base: Mapped[str] = mapped_column(String(32), nullable=False)
    display_units_json: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    modified_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True)


class CatalogMetaAudit(Base):
    """Log global de cambios sobre tablas catalog_meta_*."""

    __tablename__ = "catalog_meta_audit"
    __table_args__ = (
        Index("ix_catalog_meta_audit_table", "table_name", "row_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_name: Mapped[str] = mapped_column(String(64), nullable=False)
    row_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    diff_json: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    changed_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
