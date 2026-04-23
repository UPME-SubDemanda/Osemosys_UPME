"""Modelo ORM para la bitácora de eliminaciones."""

from __future__ import annotations

from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DeletionLog(Base):
    """Registro inmutable de cada eliminación de escenario o simulación.

    Se inserta junto con la eliminación para que aún después del hard delete
    del registro original quede rastro del qué/quién/cuándo.
    """

    __tablename__ = "deletion_log"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('SCENARIO','SIMULATION_JOB')",
            name="deletion_log_entity_type",
        ),
        Index("ix_deletion_log_deleted_at", "deleted_at"),
        Index("ix_deletion_log_entity", "entity_type", "entity_id"),
        {"schema": "osemosys"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_name: Mapped[str] = mapped_column(String(400), nullable=False)
    deleted_by_user_id: Mapped[Any] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.user.id", ondelete="RESTRICT"),
        nullable=False,
    )
    deleted_by_username: Mapped[str] = mapped_column(String(100), nullable=False)
    deleted_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    details_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
