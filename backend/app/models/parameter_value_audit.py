"""Modelo ORM para auditoría de cambios directos sobre `parameter_value`."""

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ParameterValueAudit(Base):
    """Traza de mutaciones aplicadas directamente en `parameter_value`."""

    __tablename__ = "parameter_value_audit"
    __table_args__ = {"schema": "osemosys"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_parameter_value: Mapped[int] = mapped_column(
        Integer, ForeignKey("osemosys.parameter_value.id", ondelete="RESTRICT"), nullable=False
    )
    old_value: Mapped[float] = mapped_column(Float, nullable=False)
    new_value: Mapped[float] = mapped_column(Float, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

