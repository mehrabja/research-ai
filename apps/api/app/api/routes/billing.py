"""Workspace billing checkout, invoice and webhook routes."""
from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.billing.registry import build_billing_provider
from app.billing.stripe import StripeBillingProvider
from app.core.config import get_settings
from app.core.exceptions import (
    AppError,
    AuthenticationRequired,
)
from app.db.models.billing_invoice import BillingInvoice
from app.db.models.plan import Plan
from app.db.models.subscription import Subscription
from app.db.session import get_db
from app.db.models.user import User
from app.schemas.subscription import SubscriptionRead
from app.schemas.billing import (
    ChangePlanRequest,
    CheckoutRequest,
    CheckoutResponse,
    InvoiceListResponse,
    InvoiceRead,
)
from app.services import billing as billing_service
from app.services import memberships as memberships_service
from app.services.stripe_billing import create_checkout, sync_invoice

router = APIRouter(tags=["billing"])


@router.post(
    "/workspaces/{workspace_id}/billing/checkout",
    response_model=CheckoutResponse,
)
def create_checkout_route(
    workspace_id: uuid.UUID,
    body: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CheckoutResponse:
    settings = get_settings()
    provider = build_billing_provider()

    success_url = settings.stripe_success_url
    cancel_url = settings.stripe_cancel_url
    if provider.provider_name != "stripe":
        if not success_url or not cancel_url:
            raise AppError("billing return URLs are not configured")
    result = create_checkout(
        db,
        workspace_id=workspace_id,
        actor_user_id=current_user.id,
        plan_code=body.plan_code,
        provider=provider,
        success_url=success_url,
        cancel_url=cancel_url,
    )
    db.commit()
    if not result["checkout_session_id"] or not result["checkout_url"]:
        raise AppError("billing provider returned an incomplete checkout session")
    return CheckoutResponse(**result)




@router.post(
    "/workspaces/{workspace_id}/billing/change-plan",
    response_model=SubscriptionRead,
)
def change_plan_route(
    workspace_id: uuid.UUID,
    body: ChangePlanRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionRead:
    plan = db.execute(
        select(Plan).where(Plan.code == body.plan_code, Plan.status == "active")
    ).scalar_one_or_none()
    if plan is None:
        raise billing_service.PlanNotFound()
    live = billing_service.require_live_subscription(
        db, workspace_id=workspace_id
    )
    provider = None
    if live.provider != "none" and live.provider_subscription_id:
        configured = build_billing_provider()
        if configured.provider_name != live.provider:
            raise AppError("billing provider configuration does not match the subscription")
        provider = configured
    sub = billing_service.change_plan(
        db,
        workspace_id=workspace_id,
        actor_user_id=current_user.id,
        new_plan_id=plan.id,
        provider=provider,
    )
    db.commit()
    db.refresh(sub)
    return SubscriptionRead(
        id=sub.id,
        workspace_id=sub.workspace_id,
        plan_id=sub.plan_id,
        plan_code=plan.code,
        status=sub.status,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        provider=sub.provider,
        cancel_at_period_end=sub.cancel_at_period_end,
        created_at=sub.created_at,
    )


@router.post(
    "/workspaces/{workspace_id}/billing/cancel",
    response_model=SubscriptionRead,
)
def cancel_subscription_route(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionRead:
    live = billing_service.require_live_subscription(db, workspace_id=workspace_id)
    provider = None
    if live.provider == "stripe" and live.provider_subscription_id:
        configured = build_billing_provider()
        if configured.provider_name != live.provider:
            raise AppError("billing provider configuration does not match the subscription")
        provider = configured
    sub = billing_service.cancel_subscription(
        db,
        workspace_id=workspace_id,
        actor_user_id=current_user.id,
        provider=provider,
    )
    db.commit()
    db.refresh(sub)
    plan = db.get(Plan, sub.plan_id)
    return SubscriptionRead(
        id=sub.id,
        workspace_id=sub.workspace_id,
        plan_id=sub.plan_id,
        plan_code=plan.code if plan else "",
        status=sub.status,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        provider=sub.provider,
        cancel_at_period_end=sub.cancel_at_period_end,
        created_at=sub.created_at,
    )


@router.post(
    "/workspaces/{workspace_id}/billing/resume",
    response_model=SubscriptionRead,
)
def resume_subscription_route(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionRead:
    live = billing_service.require_live_subscription(db, workspace_id=workspace_id)
    provider = None
    if live.provider == "stripe" and live.provider_subscription_id:
        configured = build_billing_provider()
        if configured.provider_name != live.provider:
            raise AppError("billing provider configuration does not match the subscription")
        provider = configured
    sub = billing_service.resume_subscription(
        db,
        workspace_id=workspace_id,
        actor_user_id=current_user.id,
        provider=provider,
    )
    db.commit()
    db.refresh(sub)
    plan = db.get(Plan, sub.plan_id)
    return SubscriptionRead(
        id=sub.id,
        workspace_id=sub.workspace_id,
        plan_id=sub.plan_id,
        plan_code=plan.code if plan else "",
        status=sub.status,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        provider=sub.provider,
        cancel_at_period_end=sub.cancel_at_period_end,
        created_at=sub.created_at,
    )


@router.get(
    "/workspaces/{workspace_id}/billing/invoices",
    response_model=InvoiceListResponse,
)
def list_invoices_route(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvoiceListResponse:
    memberships_service.require_active_membership(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    rows = list(
        db.execute(
            select(BillingInvoice)
            .where(BillingInvoice.workspace_id == workspace_id)
            .order_by(BillingInvoice.provider_created_at.desc().nullslast())
            .limit(100)
        ).scalars().all()
    )
    return InvoiceListResponse(
        items=[InvoiceRead.model_validate(row) for row in rows],
        total=len(rows),
    )


@router.post("/billing/webhooks/stripe", status_code=200)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    db: Session = Depends(__import__("app.db.session", fromlist=["get_db"]).get_db),
) -> dict[str, str]:
    if not stripe_signature:
        raise AuthenticationRequired()

    provider = build_billing_provider()
    if not isinstance(provider, StripeBillingProvider):
        raise AppError("Stripe billing provider is not active")

    raw_body = await request.body()
    if not raw_body:
        raise AppError("empty webhook body")

    event = provider.construct_webhook_event(
        raw_body=raw_body,
        signature=stripe_signature,
    )
    event_id = event.get("id")
    event_type = event.get("type")
    data = event.get("data")
    obj = data.get("object") if isinstance(data, dict) else None
    if not isinstance(event_id, str) or not isinstance(event_type, str) or not isinstance(obj, dict):
        raise AppError("invalid Stripe event envelope")

    payload_hash = hashlib.sha256(raw_body).hexdigest()
    billing_event, created = billing_service.record_billing_event(
        db,
        provider="stripe",
        provider_event_id=event_id,
        event_type=event_type,
        payload_hash=payload_hash,
    )
    if not created:
        if billing_event.status == billing_service.BILLING_EVENT_PROCESSED:
            db.commit()
            return {"status": "duplicate"}
        billing_event.status = "received"

    metadata = obj.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    workspace_raw = metadata.get("workspace_id")

    if event_type == "checkout.session.completed":
        if not isinstance(workspace_raw, str):
            raise AppError("checkout session is missing workspace metadata")
        workspace_id = uuid.UUID(workspace_raw)
        subscription_id = obj.get("subscription")
        customer_id = obj.get("customer")
        if isinstance(subscription_id, str):
            existing = db.execute(
                select(Subscription)
                .where(Subscription.provider_subscription_id == subscription_id)
                .with_for_update()
            ).scalar_one_or_none()
            if existing is not None:
                existing.provider_customer_id = (
                    customer_id if isinstance(customer_id, str) else existing.provider_customer_id
                )
        else:
            raise AppError("checkout session is missing subscription")
        billing_event.event_metadata = {
            "workspace_id": str(workspace_id),
            "checkout_session_id": str(obj.get("id", "")),
            "customer_id": str(customer_id or ""),
        }

    elif event_type.startswith("customer.subscription."):
        subscription_id = obj.get("id")
        if not isinstance(subscription_id, str):
            raise AppError("subscription event missing id")

        existing = db.execute(
            select(Subscription)
            .where(Subscription.provider == "stripe")
            .where(Subscription.provider_subscription_id == subscription_id)
            .with_for_update()
        ).scalar_one_or_none()

        if existing is None:
            if not isinstance(workspace_raw, str) or not isinstance(metadata.get("plan_code"), str):
                raise AppError("subscription event missing workspace/plan metadata")
            workspace_id = uuid.UUID(workspace_raw)
            plan = db.execute(
                select(Plan).where(Plan.code == metadata["plan_code"])
            ).scalar_one_or_none()
            if plan is None:
                raise AppError("subscription event references an unknown plan")
            existing = Subscription(
                workspace_id=workspace_id,
                plan_id=plan.id,
                status="active",
                provider="stripe",
                provider_customer_id=(
                    str(obj["customer"]) if obj.get("customer") else None
                ),
                provider_subscription_id=subscription_id,
                cancel_at_period_end=bool(obj.get("cancel_at_period_end", False)),
            )
            db.add(existing)
        status_value = obj.get("status")
        normalized = {
            "trialing": "trialing",
            "active": "active",
            "past_due": "past_due",
            "canceled": "canceled",
            "unpaid": "expired",
            "incomplete": "expired",
            "incomplete_expired": "expired",
            "paused": "expired",
        }.get(str(status_value))
        if normalized is None:
            raise AppError("unsupported provider subscription status")
        existing.status = normalized
        existing.cancel_at_period_end = bool(obj.get("cancel_at_period_end", False))
        existing.provider_customer_id = (
            str(obj["customer"]) if obj.get("customer") else existing.provider_customer_id
        )
        current_start = obj.get("current_period_start")
        current_end = obj.get("current_period_end")
        if isinstance(current_start, (int, float)):
            from datetime import UTC, datetime
            existing.current_period_start = datetime.fromtimestamp(current_start, UTC)
        if isinstance(current_end, (int, float)):
            from datetime import UTC, datetime
            existing.current_period_end = datetime.fromtimestamp(current_end, UTC)

    elif event_type in {"invoice.paid", "invoice.payment_failed", "invoice.finalized"}:
        subscription_id = obj.get("subscription")
        workspace_id = None
        if isinstance(subscription_id, str):
            sub = db.execute(
                select(Subscription).where(
                    Subscription.provider == "stripe",
                    Subscription.provider_subscription_id == subscription_id,
                )
            ).scalar_one_or_none()
            if sub is not None:
                workspace_id = sub.workspace_id
        if workspace_id is None and isinstance(metadata.get("workspace_id"), str):
            workspace_id = uuid.UUID(metadata["workspace_id"])
        if workspace_id is None:
            raise AppError("invoice event cannot be mapped to a workspace")
        sync_invoice(
            db,
            workspace_id=workspace_id,
            provider="stripe",
            payload=obj,
        )
        if event_type == "invoice.payment_failed" and isinstance(subscription_id, str):
            sub = db.execute(
                select(Subscription)
                .where(
                    Subscription.provider == "stripe",
                    Subscription.provider_subscription_id == subscription_id,
                )
                .with_for_update()
            ).scalar_one_or_none()
            if sub is not None and sub.status != "canceled":
                sub.status = "past_due"

    billing_service.mark_billing_event_processed(
        db,
        event_id=billing_event.id,
    )
    db.commit()
    return {"status": "processed"}
