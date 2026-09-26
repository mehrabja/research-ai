"""M39 billing API schemas."""
from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class BillingCheckoutRequest(BaseModel):
    plan_id: uuid.UUID
    idempotency_key: str = Field(min_length=8, max_length=200)

class BillingCheckoutResponse(BaseModel):
    checkout_session_id: str
    checkout_url: str
    status: str

class BillingInvoiceRead(BaseModel):
    model_config=ConfigDict(extra="forbid")
    id: uuid.UUID
    provider: str
    provider_invoice_id: str
    status: str
    currency: str
    amount_due: str
    amount_paid: str
    hosted_invoice_url: str | None
    invoice_pdf_url: str | None
    period_start: datetime | None
    period_end: datetime | None
    created_at: datetime

class BillingInvoiceListResponse(BaseModel):
    items: list[BillingInvoiceRead]
    total: int

class BillingPortalResponse(BaseModel):
    url: str
