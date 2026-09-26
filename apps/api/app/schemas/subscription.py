from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class SubscriptionRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    plan_id: uuid.UUID
    plan_code: str
    status: str
    current_period_start: datetime | None
    current_period_end: datetime | None
    provider: str
    cancel_at_period_end: bool
    created_at: datetime
