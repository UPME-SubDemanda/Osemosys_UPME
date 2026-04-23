"""Reporte guardado: colección ordenada de plantillas de gráficas."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReportTemplate(Base):
    """Un reporte guardado, con nombre, descripción y lista de chart-templates."""

    __tablename__ = "report_template"
    __table_args__ = (
        Index("ix_report_template_user_created", "user_id", "created_at"),
        {"schema": "osemosys"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("core.user.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    fmt: Mapped[str] = mapped_column(String(8), nullable=False, default="png")
    #: Lista ordenada de IDs de ``saved_chart_template``.
    items: Mapped[object] = mapped_column(JSONB, nullable=False, default=list)

    #: Visibilidad: ``True`` = otros usuarios lo ven (solo lectura).
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    #: Reporte oficial/destacado, editable solo por administradores
    #: (``can_manage_catalogs``). Al marcarse oficial implica visible a todos.
    is_official: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    #: Override manual de organización en categorías/subcategorías.
    #: ``null`` = modo auto (derivado del MENU de ChartSelector en el frontend).
    #: Estructura JSONB: ``{ "categories": [ { id, label, items:[...], subcategories:[...] } ] }``.
    layout: Mapped[object | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
