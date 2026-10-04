"""Stripe/local billing integration service."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.billing.protocol import BillingProvider
from app.db.models.billing_invoice import BillingInvoice
from app.db.models.plan import Plan
from app.db.models.subscription import Subscription
from app.services import memberships as memberships_service


def create_checkout(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    plan_code: str,
    provider: BillingProvider,
    success_url: str,
    cancel_url: str,
) -> dict[str, str]:
    memberships_service.require_minimum_role(
        db,
        workspace_id=workspace_id,
        user_id=actor_user_id,
        minimum="owner",
    )
    plan = db.execute(
        select(Plan).where(
            Plan.code == plan_code,
            Plan.status == "active",
        )
    ).scalar_one_or_none()
    if plan is None:
        raise ValueError("requested plan is not active")

    from app.db.models.user import User

    user = db.get(User, actor_user_id)
    if user is None:
        raise ValueError("owner user not found")

    sub = db.execute(
        select(Subscription)
        .where(
            Subscription.workspace_id == workspace_id,
            Subscription.provider_customer_id.is_not(None),
        )
        .order_by(Subscription.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    customer_id = sub.provider_customer_id if sub is not None else None
    if customer_id is None:
        customer_id = provider.create_customer(
            workspace_id=workspace_id,
            owner_user_id=actor_user_id,
            email=user.email,
            name=user.full_name,
            idempotency_key=f"billing-customer:{workspace_id}",
        )

    price_id = plan_code
    if provider.provider_name == "stripe":
        import json

        from app.core.config import get_settings

        try:
            price_map = json.loads(get_settings().stripe_price_map_json or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("invalid STRIPE_PRICE_MAP_JSON") from exc
        price_id = str(price_map.get(plan.code) or "")
        if not price_id:
            raise ValueError(f"no Stripe price configured for plan {plan.code!r}")

    session = provider.create_checkout_session(
        customer_id=customer_id,
        price_id=price_id,
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=str(workspace_id),
        metadata={
            "workspace_id": str(workspace_id),
            "plan_code": plan.code,
        },
        idempotency_key=f"checkout:{workspace_id}:{plan.code}",
    )
    return {
        "provider": provider.provider_name,
        "checkout_session_id": str(session.get("id", "")),
        "checkout_url": str(session.get("url", "")),
    }


def sync_invoice(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    provider: str,
    payload: dict,
) -> BillingInvoice:
    provider_invoice_id = payload.get("id")
    if not isinstance(provider_invoice_id, str):
        raise ValueError("invoice has no provider id")

    row = db.execute(
        select(BillingInvoice)
        .where(
            BillingInvoice.provider == provider,
            BillingInvoice.provider_invoice_id == provider_invoice_id,
        )
        .with_for_update()
    ).scalar_one_or_none()

    def dt(seconds: object) -> datetime | None:
        if not isinstance(seconds, (int, float)):
            return None
        return datetime.fromtimestamp(float(seconds), tz=UTC)

    if row is None:
        row = BillingInvoice(
            workspace_id=workspace_id,
            provider=provider,
            provider_invoice_id=provider_invoice_id,
            status=str(payload.get("status") or "unknown"),
        )
        db.add(row)

    row.provider_customer_id = (
        str(payload["customer"]) if payload.get("customer") else None
    )
    row.provider_subscription_id = (
        str(payload["subscription"])
        if payload.get("subscription")
        else None
    )
    row.status = str(payload.get("status") or row.status)
    row.currency = (
        str(payload["currency"]) if payload.get("currency") else None
    )
    amount_due = payload.get("amount_due")
    row.amount_due = (
        Decimal(amount_due) / Decimal(100) if isinstance(amount_due, int) else None
    )
    amount_paid = payload.get("amount_paid")
    row.amount_paid = (
        Decimal(amount_paid) / Decimal(100) if isinstance(amount_paid, int) else None
    )
    row.hosted_invoice_url = payload.get("hosted_invoice_url")
    row.invoice_pdf_url = payload.get("invoice_pdf")
    row.provider_created_at = dt(payload.get("created"))

    db.flush()
    return row
