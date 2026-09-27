from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class CheckoutSessionRequest(BaseModel):
    plan_code: str = Field(..., min_length=1, max_length=100)


class CheckoutSessionResponse(BaseModel):
    session_id: str
    checkout_url: str | None


class BillingPortalActionResponse(BaseModel):
    status: str
    subscription_id: uuid.UUID
    cancel_at_period_end: bool

class ChangePlanRequest(BaseModel):
    plan_code: str = Field(..., min_length=1, max_length=100)


class SubscriptionSummaryResponse(BaseModel):
    subscription: dict
