from datetime import datetime

from pydantic import BaseModel


class MosekLicenseStatus(BaseModel):
    configured: bool
    updated_at: datetime | None = None
