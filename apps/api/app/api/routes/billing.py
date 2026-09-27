from __future__ import annotations

import hashlib
import hmac
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.db.models.plan import Plan
from app.db.models.subscription import Subscription
from app.db.models.user import User
from app.db.session import get_db
from app.domain.billing import can_transition
from app.schemas.billing import (
    BillingPortalActionResponse,
    ChangePlanRequest,
    CheckoutSessionRequest,
    SubscriptionSummaryResponse,
    CheckoutSessionResponse,
)
from app.services import billing as billing_service
from app.services.billing_provider import get_billing_provider

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post(
    "/workspaces/{workspace_id}/checkout",
    response_model=CheckoutSessionResponse,
)
def create_checkout(
    workspace_id: uuid.UUID,
    body: CheckoutSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CheckoutSessionResponse:
    settings = get_settings()
    if settings.billing_provider != "stripe":
        raise billing_service.BillingOperationUnavailable()

    from app.services.workspaces import get_workspace_for_user
    _workspace, role = get_workspace_for_user(
        db, workspace_id=workspace_id, user_id=current_user.id
    )
    if role != "owner":
        raise HTTPException(status_code=403, detail="billing owner required")

    sub = billing_service.require_live_subscription(
        db, workspace_id=workspace_id
    )
    provider = get_billing_provider()

    customer_id = sub.provider_customer_id
    if not customer_id:
        customer_id = provider.create_customer(
            workspace_id=workspace_id,
            owner_user_id=current_user.id,
            idempotency_key=f"billing-customer:{workspace_id}",
        )
        sub.provider_customer_id = customer_id
        db.flush()

    create_checkout = getattr(provider, "create_checkout_session", None)
    if create_checkout is None:
        raise billing_service.BillingOperationUnavailable()

    if not settings.stripe_success_url or not settings.stripe_cancel_url:
        raise billing_service.BillingOperationUnavailable()

    payload = create_checkout(
        customer_id=customer_id,
        plan_code=body.plan_code,
        success_url=settings.stripe_success_url,
        cancel_url=settings.stripe_cancel_url,
        idempotency_key=(
            f"checkout:{workspace_id}:{body.plan_code}"
        ),
    )
    db.commit()
    session_id = payload.get("id")
    checkout_url = payload.get("url")
    if not isinstance(session_id, str):
        raise billing_service.BillingOperationUnavailable()
    return CheckoutSessionResponse(
        session_id=session_id,
        checkout_url=checkout_url if isinstance(checkout_url, str) else None,
    )


@router.get(
    "/workspaces/{workspace_id}/subscription",
    response_model=SubscriptionSummaryResponse,
)
def get_subscription(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionSummaryResponse:
    from app.services.workspaces import get_workspace_for_user
    get_workspace_for_user(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    sub = billing_service.get_live_subscription(
        db,
        workspace_id=workspace_id,
    )
    if sub is None:
        return SubscriptionSummaryResponse(subscription={})
    plan = db.get(Plan, sub.plan_id)
    return SubscriptionSummaryResponse(
        subscription={
            "id": str(sub.id),
            "workspace_id": str(sub.workspace_id),
            "plan_id": str(sub.plan_id),
            "plan_code": plan.code if plan else None,
            "status": sub.status,
            "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None,
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
            "provider": sub.provider,
            "cancel_at_period_end": sub.cancel_at_period_end,
        }
    )


@router.post(
    "/workspaces/{workspace_id}/plan",
    response_model=BillingPortalActionResponse,
)
def change_workspace_plan(
    workspace_id: uuid.UUID,
    body: ChangePlanRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BillingPortalActionResponse:
    from app.services.workspaces import get_workspace_for_user
    get_workspace_for_user(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    plan = db.execute(
        select(Plan).where(Plan.code == body.plan_code)
    ).scalar_one_or_none()
    if plan is None:
        raise billing_service.PlanNotFound()
    provider = get_billing_provider()
    sub = billing_service.change_plan(
        db,
        workspace_id=workspace_id,
        actor_user_id=current_user.id,
        new_plan_id=plan.id,
        provider=provider,
    )
    db.commit()
    return BillingPortalActionResponse(
        status=sub.status,
        subscription_id=sub.id,
        cancel_at_period_end=sub.cancel_at_period_end,
    )


@router.post(
    "/workspaces/{workspace_id}/cancel",
    response_model=BillingPortalActionResponse,
)
def cancel_workspace_subscription(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BillingPortalActionResponse:
    provider = get_billing_provider()
    sub = billing_service.cancel_subscription(
        db,
        workspace_id=workspace_id,
        actor_user_id=current_user.id,
        provider=provider,
    )
    db.commit()
    return BillingPortalActionResponse(
        status=sub.status,
        subscription_id=sub.id,
        cancel_at_period_end=sub.cancel_at_period_end,
    )


@router.post(
    "/workspaces/{workspace_id}/resume",
    response_model=BillingPortalActionResponse,
)
def resume_workspace_subscription(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BillingPortalActionResponse:
    provider = get_billing_provider()
    sub = billing_service.resume_subscription(
        db,
        workspace_id=workspace_id,
        actor_user_id=current_user.id,
        provider=provider,
    )
    db.commit()
    return BillingPortalActionResponse(
        status=sub.status,
        subscription_id=sub.id,
        cancel_at_period_end=sub.cancel_at_period_end,
    )


def _verify_stripe_signature(
    payload: bytes,
    signature: str,
    secret: str,
    *,
    tolerance_seconds: int = 300,
) -> bool:
    timestamp: int | None = None
    signatures: list[str] = []
    for part in signature.split(","):
        key, _, value = part.partition("=")
        if key == "t":
            try:
                timestamp = int(value)
            except ValueError:
                return False
        elif key == "v1" and value:
            signatures.append(value)
    if timestamp is None or not signatures:
        return False
    if abs(int(time.time()) - timestamp) > tolerance_seconds:
        return False
    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(
        secret.encode("utf-8"),
        signed,
        hashlib.sha256,
    ).hexdigest()
    return any(
        hmac.compare_digest(expected, candidate)
        for candidate in signatures
    )


@router.post("/webhooks/stripe", status_code=status.HTTP_204_NO_CONTENT)
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> None:
    settings = get_settings()
    if settings.billing_provider != "stripe":
        raise HTTPException(status_code=404, detail="billing webhook unavailable")
    body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    if not _verify_stripe_signature(
        body,
        signature,
        settings.stripe_webhook_secret,
    ):
        raise HTTPException(status_code=400, detail="invalid signature")

    import json

    try:
        event = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid JSON") from exc

    event_id = event.get("id")
    event_type = event.get("type")
    if not isinstance(event_id, str) or not isinstance(event_type, str):
        raise HTTPException(status_code=400, detail="invalid event")

    payload_hash = hashlib.sha256(body).hexdigest()
    inbox, created = billing_service.record_billing_event(
        db,
        provider="stripe",
        provider_event_id=event_id,
        event_type=event_type,
        payload_hash=payload_hash,
    )
    if not created:
        db.commit()
        return

    obj = (event.get("data") or {}).get("object") or {}
    stripe_subscription_id = obj.get("id")
    stripe_customer_id = obj.get("customer")

    if (
        event_type.startswith("customer.subscription.")
        and isinstance(stripe_subscription_id, str)
    ):
        sub = db.execute(
            select(Subscription).where(
                Subscription.provider == "stripe",
                Subscription.provider_subscription_id == stripe_subscription_id,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if sub is not None:
            status_value = obj.get("status")
            cancel_at_period_end = bool(obj.get("cancel_at_period_end"))
            if isinstance(status_value, str):
                allowed = {
                    "trialing": "trialing",
                    "active": "active",
                    "past_due": "past_due",
                    "canceled": "canceled",
                    "incomplete_expired": "expired",
                }
                new_status = allowed.get(status_value)
                if new_status is not None:
                    current = sub.status
                    if can_transition(current, new_status):
                        sub.status = new_status
                    elif current == new_status:
                        pass
                    else:
                        inbox.status = "failed"
                        db.commit()
                        return
                sub.cancel_at_period_end = cancel_at_period_end
                if isinstance(stripe_customer_id, str):
                    sub.provider_customer_id = stripe_customer_id

    billing_service.mark_billing_event_processed(
        db,
        event_id=inbox.id,
    )
    db.commit()
