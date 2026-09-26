"""M37 — Plans and entitlements."""
from __future__ import annotations

import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPKMixin
from app.domain.plan import FEATURES, PLAN_STATUSES


def _in_check(col: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(
        f"{col} IN (" + ",".join(f"'{v}'" for v in values) + ")",
        name=name,
    )


# SQL fragment enforcing unit ↔ feature consistency at the DB level.
# Kept as a module constant so the migration can reuse it verbatim.
_UNIT_MATCH_SQL = (
    "unit = CASE feature "
    "  WHEN 'storage.bytes'       THEN 'bytes' "
    "  WHEN 'ai_generation_units' THEN 'units' "
    "  WHEN 'search.requests'     THEN 'requests' "
    "  ELSE 'count' "
    "END"
)


class Plan(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'active'")
    )

    __table_args__ = (
        _in_check("status", PLAN_STATUSES, "ck_plans_status"),
        Index("ux_plans_code", "code", unique=True),
    )


class PlanEntitlement(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "plan_entitlements"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    feature: Mapped[str] = mapped_column(Text, nullable=False)
    # NULL == unlimited.
    limit_value: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    unit: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        _in_check("feature", FEATURES, "ck_plan_entitlements_feature"),
        CheckConstraint(
            "limit_value IS NULL OR limit_value >= 0",
            name="ck_plan_entitlements_limit_nonneg",
        ),
        CheckConstraint(
            _UNIT_MATCH_SQL,
            name="ck_plan_entitlements_unit",
        ),
        UniqueConstraint(
            "plan_id",
            "feature",
            name="ux_plan_entitlements_plan_feature",
        ),
        Index("ix_plan_entitlements_plan", "plan_id"),
    )
