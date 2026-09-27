"""M37 Phase 2-F — local-authoritative subscription service.

The ``subscriptions`` table is the source of truth for application
state.  Provider-specific fields (``provider_customer_id``,
``provider_subscription_id``) are integration metadata only.

No route or service imports a real provider SDK.  Real provider
wiring belongs to M40.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.billing.protocol import BillingProvider
from app.core.exceptions import (
    AppError,
)
from app.db.models.billing_event import BillingEvent
from app.db.models.plan import Plan
from app.db.models.subscription import Subscription
from app.domain.billing import (
    ACTIVE_SUBSCRIPTION_STATUSES,
    BILLING_EVENT_PROCESSED,
    SUB_CANCELED,
    can_transition,
)
from app.services import memberships as memberships_service
from app.services.audit import emit_audit


def get_billing_provider() -> BillingProvider | None:
    from app.core.config import get_settings
    from app.providers.registry import ProviderCapability, resolve_provider

    settings = get_settings()
    if settings.billing_provider == "none":
        return None
    return resolve_provider(
        capability=ProviderCapability.BILLING,
        preferred=settings.billing_provider,
    )


class BillingOperationUnavailable(AppError):
    code = "BILLING_OPERATION_UNAVAILABLE"
    status_code = 503
    message = "Billing operation is unavailable."


class SubscriptionNotFound(AppError):
    code = "SUBSCRIPTION_NOT_FOUND"
    status_code = 404
    message = "Subscription not found."


class SubscriptionStateInvalid(AppError):
    code = "SUBSCRIPTION_STATE_INVALID"
    status_code = 409
    message = "Subscription state transition is not allowed."


class PlanNotFound(AppError):
    code = "PLAN_NOT_FOUND"
    status_code = 404
    message = "Plan not found."


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------

def get_live_subscription(
    db: Session, *, workspace_id: uuid.UUID
) -> Subscription | None:
    return db.execute(
        select(Subscription).where(
            Subscription.workspace_id == workspace_id,
            Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
        )
    ).scalar_one_or_none()


def require_live_subscription(
    db: Session, *, workspace_id: uuid.UUID
) -> Subscription:
    sub = get_live_subscription(db, workspace_id=workspace_id)
    if sub is None:
        raise SubscriptionNotFound()
    return sub


# --------------------------------------------------------------------------
# Plan change
# --------------------------------------------------------------------------

def change_plan(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    new_plan_id: uuid.UUID,
    provider: BillingProvider | None = None,
) -> Subscription:
    """Owner-only plan swap on the live subscription.

    Usage history is never overwritten; new quota resolutions simply
    read the new plan's entitlements from the next call onward.
    """
    memberships_service.require_minimum_role(
        db,
        workspace_id=workspace_id,
        user_id=actor_user_id,
        minimum="owner",
    )
    sub = require_live_subscription(db, workspace_id=workspace_id)

    plan = db.get(Plan, new_plan_id)
    if plan is None:
        raise PlanNotFound()

    if sub.plan_id == new_plan_id:
        return sub

    old_plan_id = sub.plan_id
    old_plan = db.get(Plan, old_plan_id)
    if provider is not None and sub.provider_subscription_id:
        new_plan = db.get(Plan, new_plan_id)
        if new_plan is None:
            raise PlanNotFound()
        provider.update_subscription_plan(
            subscription_id=sub.provider_subscription_id,
            plan_code=new_plan.code,
            idempotency_key=(
                f"subscription-plan:{workspace_id}:{old_plan_id}:{new_plan_id}"
            ),
        )
    sub.plan_id = new_plan_id
    db.flush()

    emit_audit(
        "PLAN_CHANGED",
        user_id=str(actor_user_id),
        workspace_id=str(workspace_id),
        subscription_id=str(sub.id),
        reason=str(old_plan_id),
        outcome=str(new_plan_id),
    )
    return sub


# --------------------------------------------------------------------------
# Status transitions
# --------------------------------------------------------------------------

def transition_status(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    new_status: str,
    actor_user_id: uuid.UUID | None = None,
) -> Subscription:
    sub = require_live_subscription(db, workspace_id=workspace_id)
    if not can_transition(sub.status, new_status):
        raise SubscriptionStateInvalid(
            f"cannot transition {sub.status} -> {new_status}"
        )
    if sub.status == new_status:
        return sub
    previous_status = sub.status
    sub.status = new_status
    db.flush()
    emit_audit(
        "SUBSCRIPTION_CHANGED",
        user_id=str(actor_user_id) if actor_user_id else None,
        workspace_id=str(workspace_id),
        subscription_id=str(sub.id),
        from_role=previous_status,
        to_role=new_status,
    )
    return sub


# --------------------------------------------------------------------------
# Cancel / resume (local state; provider call is a no-op in M37)
# --------------------------------------------------------------------------

def cancel_subscription(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    provider: BillingProvider | None = None,
) -> Subscription:
    memberships_service.require_minimum_role(
        db,
        workspace_id=workspace_id,
        user_id=actor_user_id,
        minimum="owner",
    )
    sub = require_live_subscription(db, workspace_id=workspace_id)
    sub.cancel_at_period_end = True
    if provider is not None and sub.provider_subscription_id:
        provider.cancel_subscription(
            subscription_id=sub.provider_subscription_id,
            at_period_end=True,
        )
    db.flush()
    emit_audit(
        "SUBSCRIPTION_CANCELED",
        user_id=str(actor_user_id),
        workspace_id=str(workspace_id),
        subscription_id=str(sub.id),
    )
    return sub


def resume_subscription(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    provider: BillingProvider | None = None,
) -> Subscription:
    memberships_service.require_minimum_role(
        db,
        workspace_id=workspace_id,
        user_id=actor_user_id,
        minimum="owner",
    )
    sub = require_live_subscription(db, workspace_id=workspace_id)
    if sub.status == SUB_CANCELED:
        raise SubscriptionStateInvalid()
    sub.cancel_at_period_end = False
    if provider is not None and sub.provider_subscription_id:
        provider.resume_subscription(
            subscription_id=sub.provider_subscription_id,
        )
    db.flush()
    emit_audit(
        "SUBSCRIPTION_RESUMED",
        user_id=str(actor_user_id),
        workspace_id=str(workspace_id),
        subscription_id=str(sub.id),
    )
    return sub


# --------------------------------------------------------------------------
# Billing event inbox (webhook foundation)
# --------------------------------------------------------------------------

def record_billing_event(
    db: Session,
    *,
    provider: str,
    provider_event_id: str,
    event_type: str,
    payload_hash: str,
) -> tuple[BillingEvent, bool]:
    """Idempotent insert.  Returns ``(event, created)``.

    Duplicate ``(provider, provider_event_id)`` returns the existing
    row with ``created=False``.
    """
    existing = db.execute(
        select(BillingEvent).where(
            BillingEvent.provider == provider,
            BillingEvent.provider_event_id == provider_event_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False
    ev = BillingEvent(
        provider=provider,
        provider_event_id=provider_event_id,
        event_type=event_type,
        payload_hash=payload_hash,
    )
    db.add(ev)
    db.flush()
    return ev, True


def mark_billing_event_processed(
    db: Session, *, event_id: uuid.UUID
) -> BillingEvent:
    ev = db.get(BillingEvent, event_id)
    if ev is None:
        raise SubscriptionNotFound()  # 404 convention
    ev.status = BILLING_EVENT_PROCESSED
    ev.processed_at = datetime.now(UTC)
    db.flush()
    return ev


__all__ = [
    "BillingOperationUnavailable",
    "PlanNotFound",
    "SubscriptionNotFound",
    "SubscriptionStateInvalid",
    "cancel_subscription",
    "change_plan",
    "get_billing_provider",
    "get_live_subscription",
    "mark_billing_event_processed",
    "record_billing_event",
    "require_live_subscription",
    "resume_subscription",
    "transition_status",
]
