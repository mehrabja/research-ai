from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class EntitlementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    feature: str
    limit_value: int | None
    unit: str


class PlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    status: str
    entitlements: list[EntitlementRead]
