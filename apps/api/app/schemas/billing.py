"""Billing checkout and invoice API schemas."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import uuid

from pydantic import BaseModel, Field


class CheckoutRequest(BaseModel):
    plan_code: str = Field(..., min_length=1, max_length=64)


class CheckoutResponse(BaseModel):
    provider: str
    checkout_session_id: str
    checkout_url: str


class InvoiceRead(BaseModel):
    id: uuid.UUID | None = None
    provider: str
    provider_invoice_id: str
    status: str
    currency: str | None
    amount_due: Decimal | None
    amount_paid: Decimal | None
    hosted_invoice_url: str | None
    invoice_pdf_url: str | None
    provider_created_at: datetime | None


class InvoiceListResponse(BaseModel):
    items: list[InvoiceRead]
    total: int
