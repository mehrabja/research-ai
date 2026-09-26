"""M39 normalized billing provider records."""
from __future__ import annotations
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, Index, Numeric, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPKMixin

class BillingCustomer(Base, UUIDPKMixin, CreatedAtMixin, TimestampMixin):
    __tablename__="billing_customers"
    workspace_id: Mapped[uuid.UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("workspaces.id",ondelete="CASCADE"),nullable=False,unique=True)
    provider: Mapped[str]=mapped_column(Text,nullable=False)
    provider_customer_id: Mapped[str]=mapped_column(Text,nullable=False)
    __table_args__=(UniqueConstraint("provider","provider_customer_id",name="ux_billing_customers_provider_customer"),Index("ix_billing_customers_workspace","workspace_id"))

class BillingCheckoutSession(Base, UUIDPKMixin, CreatedAtMixin, TimestampMixin):
    __tablename__="billing_checkout_sessions"
    workspace_id: Mapped[uuid.UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("workspaces.id",ondelete="CASCADE"),nullable=False)
    plan_id: Mapped[uuid.UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("plans.id",ondelete="RESTRICT"),nullable=False)
    provider: Mapped[str]=mapped_column(Text,nullable=False)
    provider_session_id: Mapped[str]=mapped_column(Text,nullable=False)
    status: Mapped[str]=mapped_column(Text,nullable=False,server_default=text("'created'"))
    checkout_url: Mapped[str|None]=mapped_column(Text)
    idempotency_key: Mapped[str]=mapped_column(Text,nullable=False,unique=True)
    __table_args__=(UniqueConstraint("provider","provider_session_id",name="ux_billing_checkout_provider_session"),Index("ix_billing_checkout_workspace_created","workspace_id","created_at"))

class BillingInvoice(Base, UUIDPKMixin, CreatedAtMixin, TimestampMixin):
    __tablename__="billing_invoices"
    workspace_id: Mapped[uuid.UUID]=mapped_column(PGUUID(as_uuid=True),ForeignKey("workspaces.id",ondelete="CASCADE"),nullable=False)
    provider: Mapped[str]=mapped_column(Text,nullable=False)
    provider_invoice_id: Mapped[str]=mapped_column(Text,nullable=False)
    status: Mapped[str]=mapped_column(Text,nullable=False)
    currency: Mapped[str]=mapped_column(Text,nullable=False)
    amount_due: Mapped[Decimal]=mapped_column(Numeric(18,8),nullable=False,server_default=text("0"))
    amount_paid: Mapped[Decimal]=mapped_column(Numeric(18,8),nullable=False,server_default=text("0"))
    hosted_invoice_url: Mapped[str|None]=mapped_column(Text)
    invoice_pdf_url: Mapped[str|None]=mapped_column(Text)
    period_start: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    provider_metadata: Mapped[dict|None]=mapped_column("metadata",JSONB)
    __table_args__=(UniqueConstraint("provider","provider_invoice_id",name="ux_billing_invoices_provider_invoice"),Index("ix_billing_invoices_workspace_created","workspace_id","created_at"))
