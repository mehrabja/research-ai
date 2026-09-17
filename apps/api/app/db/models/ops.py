from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPKMixin


def _in_check(
    column: str, values: tuple[str, ...], name: str
) -> CheckConstraint:
    return CheckConstraint(
        f"{column} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


class UsageLog(Base, UUIDPKMixin, CreatedAtMixin):
    """Append-only audit of every metered call.

    ``report_id`` uses ON DELETE SET NULL on purpose: usage history must
    survive report deletion / anonymization.
    """

    __tablename__ = "usage_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="SET NULL"),
        nullable=True,
    )
    phase: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd_raw: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 8), nullable=True
    )
    cost_usd_charged: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 8), nullable=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        Text, nullable=True, unique=True
    )
    trace_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    # SQLAlchemy reserves `metadata`, so the Python attribute is
    # `log_metadata`. The underlying column is named `metadata`.
    log_metadata: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_usage_logs_input_tokens",
        ),
        CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_usage_logs_output_tokens",
        ),
        Index("ix_usage_logs_user_created", "user_id", "created_at"),
        Index("ix_usage_logs_report_created", "report_id", "created_at"),
        Index("ix_usage_logs_trace_id", "trace_id"),
    )


class ModelPricing(Base, UUIDPKMixin):
    __tablename__ = "model_pricing"

    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    input_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False
    )
    output_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_model_pricing_effective_range",
        ),
        Index(
            "ix_model_pricing_provider_model_effective_from",
            "provider", "model", "effective_from",
        ),
    )


class CreditTransaction(Base, UUIDPKMixin, CreatedAtMixin):
    """Append-only financial ledger.

    This table is the *only* source of truth for money. There is no
    authoritative mutable ``credits.balance`` column anywhere.
    """

    __tablename__ = "credit_transactions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'posted'")
    )

    __table_args__ = (
        _in_check(
            "type",
            ("purchase", "reserve", "settlement", "release", "refund"),
            "ck_credit_transactions_type",
        ),
        _in_check(
            "status",
            ("pending", "posted", "failed", "reversed"),
            "ck_credit_transactions_status",
        ),
        CheckConstraint(
            "amount >= 0", name="ck_credit_transactions_amount_nonneg"
        ),
        Index(
            "ix_credit_transactions_user_created", "user_id", "created_at"
        ),
        Index("ix_credit_transactions_reference", "reference"),
    )
