"""M39 billing HTTP API and authenticated Stripe webhook."""
from __future__ import annotations
import hashlib
import uuid
from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.core.exceptions import AppError
from app.db.models.billing_event import BillingEvent
from app.db.models.user import User
from app.db.session import get_db
from app.domain.billing import BILLING_EVENT_RECEIVED, PROVIDERS
from app.integrations.billing.stripe import StripeBillingProvider
from app.schemas.billing import BillingCheckoutRequest, BillingCheckoutResponse, BillingInvoiceListResponse, BillingInvoiceRead, BillingPortalResponse
from app.services import billing_provider

router=APIRouter(tags=["billing"])

@router.post("/workspaces/{workspace_id}/billing/checkout",response_model=BillingCheckoutResponse)
def checkout(workspace_id:uuid.UUID,body:BillingCheckoutRequest,current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->BillingCheckoutResponse:
    result=billing_provider.create_checkout(db,workspace_id=workspace_id,actor_user_id=current_user.id,plan_id=body.plan_id,idempotency_key=body.idempotency_key)
    return BillingCheckoutResponse(**result)

@router.post("/workspaces/{workspace_id}/billing/portal",response_model=BillingPortalResponse)
def portal(workspace_id:uuid.UUID,current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->BillingPortalResponse:
    return BillingPortalResponse(url=billing_provider.create_portal(db,workspace_id=workspace_id,actor_user_id=current_user.id))

@router.get("/workspaces/{workspace_id}/billing/invoices",response_model=BillingInvoiceListResponse)
def invoices(workspace_id:uuid.UUID,current_user:User=Depends(get_current_user),db:Session=Depends(get_db))->BillingInvoiceListResponse:
    rows=billing_provider.sync_invoices(db,workspace_id=workspace_id,actor_user_id=current_user.id)
    return BillingInvoiceListResponse(items=[BillingInvoiceRead(id=x.id,provider=x.provider,provider_invoice_id=x.provider_invoice_id,status=x.status,currency=x.currency,amount_due=str(x.amount_due),amount_paid=str(x.amount_paid),hosted_invoice_url=x.hosted_invoice_url,invoice_pdf_url=x.invoice_pdf_url,period_start=x.period_start,period_end=x.period_end,created_at=x.created_at) for x in rows],total=len(rows))

@router.post("/billing/webhooks/stripe",status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request:Request,
    stripe_signature:str|None=Header(default=None,alias="Stripe-Signature"),
    db:Session=Depends(get_db),
)->dict[str,str]:
    if not stripe_signature:
        raise AppError("Missing Stripe-Signature header.",code="BILLING_WEBHOOK_UNAUTHENTICATED",status_code=400)
    payload=await request.body()
    provider=StripeBillingProvider()
    event=provider.verify_webhook(payload=payload,signature=stripe_signature)
    event_id=str(event["id"]); event_type=str(event["type"])
    payload_hash=hashlib.sha256(payload).hexdigest()
    stored,created=billing_service.record_billing_event(
        db,provider=provider.provider_name,provider_event_id=event_id,event_type=event_type,payload_hash=payload_hash
    )
    if not created:
        db.rollback()
        return {"status":"already_processed"}
    stored.status=BILLING_EVENT_RECEIVED
    stored.event_metadata={"event_type":event_type,"livemode":bool(event.get("livemode",False)),"object_id":event.get("data",{}).get("object",{}).get("id") if isinstance(event.get("data"),dict) else None}
    try:
        billing_provider.apply_stripe_event(db,event)
        billing_service.mark_billing_event_processed(db,event_id=stored.id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"status":"processed"}
