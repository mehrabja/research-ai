"""M37 — Billing provider event inbox (provider-agnostic)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPKMixin
from app.domain.billing import BILLING_EVENT_STATUSES, PROVIDERS


def _in_check(col: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(
        f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class BillingEvent(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "billing_events"

    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_event_id: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload_hash: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'received'")
    )
    event_metadata: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    __table_args__ = (
        _in_check("provider", PROVIDERS, "ck_billing_events_provider"),
        _in_check(
            "status", BILLING_EVENT_STATUSES,
            "ck_billing_events_status",
        ),
        CheckConstraint(
            "char_length(payload_hash) = 64",
            name="ck_billing_events_payload_hash_len",
        ),
        UniqueConstraint(
            "provider",
            "provider_event_id",
            name="ux_billing_events_provider_event",
        ),
        Index("ix_billing_events_status", "status", "received_at"),
    )
