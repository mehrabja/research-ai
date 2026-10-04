"""Locally indexed billing invoices from the provider."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class BillingInvoice(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "billing_invoices"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_invoice_id: Mapped[str] = mapped_column(Text, nullable=False)
    provider_customer_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_subscription_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount_due: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    amount_paid: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    hosted_invoice_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_invoice_id",
            name="ux_billing_invoices_provider_id",
        ),
        Index("ix_billing_invoices_workspace_created", "workspace_id", "created_at"),
    )
