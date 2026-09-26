"""M37 — Provider-agnostic subscription state."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.domain.billing import PROVIDERS, SUBSCRIPTION_STATUSES


def _in_check(col: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(
        f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class Subscription(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "subscriptions"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'active'")
    )
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provider: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'none'")
    )
    provider_customer_id: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    provider_subscription_id: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    __table_args__ = (
        _in_check(
            "status", SUBSCRIPTION_STATUSES, "ck_subscriptions_status",
        ),
        _in_check("provider", PROVIDERS, "ck_subscriptions_provider"),
        CheckConstraint(
            "current_period_end IS NULL "
            "OR current_period_start IS NULL "
            "OR current_period_end > current_period_start",
            name="ck_subscriptions_period_order",
        ),
        # At most one live subscription per workspace.
        Index(
            "ux_subscriptions_active_workspace",
            "workspace_id",
            unique=True,
            postgresql_where=text(
                "status IN ('trialing','active','past_due')"
            ),
        ),
        Index("ix_subscriptions_workspace", "workspace_id"),
        Index(
            "ix_subscriptions_provider_customer",
            "provider",
            "provider_customer_id",
        ),
    )
