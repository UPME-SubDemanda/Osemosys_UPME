"""MOSEK license ciphertexts, scoped globally or to an individual user."""

import uuid

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SolverLicense(Base):
    __tablename__ = "solver_license"
    __table_args__ = ({"schema": "core"},)

    # "global" for the shared license, or "user:<uuid>" for a personal one.
    scope_key: Mapped[str] = mapped_column(String(48), primary_key=True)
    encrypted_content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("core.user.id", ondelete="SET NULL"), nullable=True
    )
