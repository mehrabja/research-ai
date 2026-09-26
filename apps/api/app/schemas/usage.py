from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class UsageItem(BaseModel):
    metric: str
    current: int
    limit: int | None
    unit: str


class UsageResponse(BaseModel):
    workspace_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    items: list[UsageItem]
