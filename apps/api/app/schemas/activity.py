from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ActivityItem(BaseModel):
    id: str
    event: str
    summary: str
    occurred_at: datetime
