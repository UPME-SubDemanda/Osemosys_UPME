"""Schemas Pydantic para la bitácora de eliminaciones."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.pagination import PaginationMeta


class DeletionLogPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_id: int
    entity_name: str
    deleted_by_user_id: str
    deleted_by_username: str
    deleted_at: datetime
    details_json: dict[str, Any] | None = None


class DeletionLogPage(BaseModel):
    data: list[DeletionLogPublic]
    meta: PaginationMeta
