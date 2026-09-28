"""Stripe webhook ingress with signature verification and idempotent inbox."""
from __future__ import annotations

import hashlib
import hmac
import json
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.subscription import Subscription
from app.db.session import get_db
from app.services import billing as billing_service

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _verify_stripe_signature(
    payload: bytes,
    signature: str,
    secret: str,
    tolerance_seconds: int = 300,
) -> dict[str, str]:
    pieces: dict[str, str] = {}
    for item in signature.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        pieces[key] = value
    timestamp_raw = pieces.get("t")
    provided = pieces.get("v1")
    if not timestamp_raw or not provided:
        raise HTTPException(status_code=400, detail="invalid webhook signature")
    try:
        timestamp = int(timestamp_raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid webhook timestamp") from exc
    if abs(int(time.time()) - timestamp) > tolerance_seconds:
        raise HTTPException(status_code=400, detail="stale webhook signature")

    signed = f"{timestamp}.{payload.decode('utf-8')}".encode()
    expected = hmac.new(
        secret.encode("utf-8"),
        signed,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=400, detail="invalid webhook signature")
    return pieces


def _subscription_status_from_stripe(value: str) -> str:
    mapping = {
        "trialing": "trialing",
        "active": "active",
        "past_due": "past_due",
        "canceled": "canceled",
        "unpaid": "past_due",
        "incomplete": "past_due",
        "incomplete_expired": "expired",
        "paused": "past_due",
    }
    return mapping.get(value, "expired")


@router.post("/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(
        default=None,
        alias="Stripe-Signature",
    ),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Stripe webhook is not configured")
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Stripe-Signature header missing")

    payload = await request.body()
    _verify_stripe_signature(
        payload,
        stripe_signature,
        settings.stripe_webhook_secret,
    )

    try:
        event = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid webhook JSON") from exc
    if not isinstance(event, dict):
        raise HTTPException(status_code=400, detail="invalid webhook payload")

    event_id = event.get("id")
    event_type = event.get("type")
    obj = ((event.get("data") or {}).get("object") or {})
    if not isinstance(event_id, str) or not isinstance(event_type, str):
        raise HTTPException(status_code=400, detail="webhook event id/type missing")
    payload_hash = hashlib.sha256(payload).hexdigest()

    billing_event, created = billing_service.record_billing_event(
        db,
        provider="stripe",
        provider_event_id=event_id,
        event_type=event_type,
        payload_hash=payload_hash,
    )
    if not created and billing_event.status == "processed":
        db.commit()
        return {"received": True, "duplicate": True}

    # Stripe subscription objects carry our workspace in customer metadata.
    # We first use provider subscription ID, then customer ID as a fallback.
    provider_subscription_id = obj.get("id") if isinstance(obj, dict) else None
    provider_customer_id = obj.get("customer") if isinstance(obj, dict) else None

    if event_type == "checkout.session.completed":
        subscription_id = obj.get("subscription")
        customer_id = obj.get("customer")
        if isinstance(customer_id, str):
            subscription = db.query(Subscription).filter(
                Subscription.provider == "stripe",
                Subscription.provider_customer_id == customer_id,
            ).first()
            if subscription is not None and isinstance(subscription_id, str):
                subscription.provider_subscription_id = subscription_id
                db.flush()

    if event_type == "invoice.payment_failed":
        customer_id = obj.get("customer")
        if isinstance(customer_id, str):
            subscription = db.query(Subscription).filter(
                Subscription.provider == "stripe",
                Subscription.provider_customer_id == customer_id,
            ).first()
            if subscription is not None and subscription.status in (
                "trialing",
                "active",
            ):
                subscription.status = "past_due"
                db.flush()

    if event_type.startswith("customer.subscription.") and (
        provider_subscription_id or provider_customer_id
    ):
        subscription = None
        if provider_subscription_id:
            subscription = db.query(Subscription).filter(
                Subscription.provider == "stripe",
                Subscription.provider_subscription_id == provider_subscription_id,
            ).first()
        if subscription is None and provider_customer_id:
            subscription = db.query(Subscription).filter(
                Subscription.provider == "stripe",
                Subscription.provider_customer_id == provider_customer_id,
            ).first()

        if subscription is not None:
            state = _subscription_status_from_stripe(
                str(obj.get("status") or "canceled")
            )
            subscription.status = state
            subscription.cancel_at_period_end = bool(
                obj.get("cancel_at_period_end", False)
            )
            subscription.provider_subscription_id = (
                provider_subscription_id or subscription.provider_subscription_id
            )
            period_start = obj.get("current_period_start")
            period_end = obj.get("current_period_end")
            from datetime import UTC, datetime
            if isinstance(period_start, int):
                subscription.current_period_start = datetime.fromtimestamp(period_start, UTC)
            if isinstance(period_end, int):
                subscription.current_period_end = datetime.fromtimestamp(period_end, UTC)
            db.flush()

    billing_service.mark_billing_event_processed(
        db,
        event_id=billing_event.id,
    )
    db.commit()
    return {"received": True}
