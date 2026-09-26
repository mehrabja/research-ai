"""M39 billing provider orchestration."""
from __future__ import annotations
import uuid
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.exceptions import AppError, InsufficientRole
from app.db.models.billing_extra import BillingCheckoutSession, BillingCustomer, BillingInvoice
from app.db.models.plan import Plan
from app.db.models.subscription import Subscription
from app.db.models.user import User
from app.domain.membership import ROLE_OWNER
from app.integrations.billing.base import BillingProvider
from app.integrations.billing.stripe import StripeBillingProvider
from app.services import billing as local_billing
from app.services import memberships as memberships_service

class BillingNotConfigured(AppError):
    code="BILLING_NOT_CONFIGURED"; status_code=503; message="Billing provider is not configured."
class BillingPlanUnavailable(AppError):
    code="BILLING_PLAN_UNAVAILABLE"; status_code=422; message="The selected plan is not available for billing."

def get_provider() -> BillingProvider:
    s=get_settings()
    if s.billing_provider=="stripe":
        return StripeBillingProvider()
    raise BillingNotConfigured()

def _price_for_plan(plan_code:str)->str:
    s=get_settings()
    value={"pro":s.stripe_price_id_pro,"team":s.stripe_price_id_team}.get(plan_code,"")
    if not value:
        raise BillingPlanUnavailable()
    return value

def ensure_customer(db:Session, *, workspace_id:uuid.UUID, owner_user:User, provider:BillingProvider)->BillingCustomer:
    row=db.execute(select(BillingCustomer).where(BillingCustomer.workspace_id==workspace_id,BillingCustomer.provider==provider.provider_name)).scalar_one_or_none()
    if row is not None:
        return row
    cid=provider.create_customer(workspace_id=workspace_id,owner_user_id=owner_user.id,email=owner_user.email,idempotency_key=f"billing-customer:{workspace_id}:{provider.provider_name}")
    row=BillingCustomer(workspace_id=workspace_id,provider=provider.provider_name,provider_customer_id=cid)
    db.add(row);db.flush()
    return row

def create_checkout(db:Session, *, workspace_id:uuid.UUID, actor_user_id:uuid.UUID, plan_id:uuid.UUID, idempotency_key:str)->dict:
    memberships_service.require_minimum_role(db,workspace_id=workspace_id,user_id=actor_user_id,minimum=ROLE_OWNER)
    plan=db.get(Plan,plan_id)
    if plan is None or plan.status!="active": raise BillingPlanUnavailable()
    owner=db.get(User,actor_user_id)
    if owner is None: raise BillingNotConfigured()
    existing=db.execute(select(BillingCheckoutSession).where(BillingCheckoutSession.idempotency_key==idempotency_key)).scalar_one_or_none()
    if existing is not None:
        return {"checkout_session_id":existing.provider_session_id,"checkout_url":existing.checkout_url,"status":existing.status}
    provider=get_provider()
    customer=ensure_customer(db,workspace_id=workspace_id,owner_user=owner,provider=provider)
    s=get_settings()
    result=provider.create_checkout_session(customer_id=customer.provider_customer_id,customer_email=owner.email,price_id=_price_for_plan(plan.code),workspace_id=workspace_id,success_url=s.stripe_success_url,cancel_url=s.stripe_cancel_url,idempotency_key=idempotency_key)
    session_id=result.get("id"); url=result.get("url"); status_value=result.get("status","open")
    if not isinstance(session_id,str) or not isinstance(url,str):
        raise BillingNotConfigured("Billing provider did not return a checkout session URL.")
    row=BillingCheckoutSession(workspace_id=workspace_id,plan_id=plan.id,provider=provider.provider_name,provider_session_id=session_id,status=str(status_value),checkout_url=url,idempotency_key=idempotency_key)
    db.add(row);db.commit()
    return {"checkout_session_id":session_id,"checkout_url":url,"status":str(status_value)}

def create_portal(db:Session, *, workspace_id:uuid.UUID, actor_user_id:uuid.UUID)->str:
    memberships_service.require_minimum_role(db,workspace_id=workspace_id,user_id=actor_user_id,minimum=ROLE_OWNER)
    provider=get_provider()
    customer=db.execute(select(BillingCustomer).where(BillingCustomer.workspace_id==workspace_id,BillingCustomer.provider==provider.provider_name)).scalar_one_or_none()
    if customer is None: raise BillingNotConfigured("No billing customer exists for this workspace.")
    return provider.create_portal_session(customer_id=customer.provider_customer_id,return_url=get_settings().stripe_portal_return_url)

def sync_invoices(db:Session, *, workspace_id:uuid.UUID, actor_user_id:uuid.UUID)->list[BillingInvoice]:
    memberships_service.require_minimum_role(db,workspace_id=workspace_id,user_id=actor_user_id,minimum=ROLE_OWNER)
    provider=get_provider()
    customer=db.execute(select(BillingCustomer).where(BillingCustomer.workspace_id==workspace_id,BillingCustomer.provider==provider.provider_name)).scalar_one_or_none()
    if customer is None: return []
    for item in provider.list_invoices(customer_id=customer.provider_customer_id):
        invoice_id=item.get("id")
        if not isinstance(invoice_id,str): continue
        row=db.execute(select(BillingInvoice).where(BillingInvoice.provider==provider.provider_name,BillingInvoice.provider_invoice_id==invoice_id)).scalar_one_or_none()
        if row is None:
            row=BillingInvoice(workspace_id=workspace_id,provider=provider.provider_name,provider_invoice_id=invoice_id,status=str(item.get("status") or "unknown"),currency=str(item.get("currency") or "usd"),amount_due=Decimal(int(item.get("amount_due") or 0))/Decimal(100),amount_paid=Decimal(int(item.get("amount_paid") or 0))/Decimal(100),hosted_invoice_url=item.get("hosted_invoice_url"),invoice_pdf_url=item.get("invoice_pdf"),provider_metadata={"livemode":bool(item.get("livemode",False))})
            db.add(row)
        else:
            row.status=str(item.get("status") or row.status)
            row.amount_due=Decimal(int(item.get("amount_due") or 0))/Decimal(100)
            row.amount_paid=Decimal(int(item.get("amount_paid") or 0))/Decimal(100)
            row.hosted_invoice_url=item.get("hosted_invoice_url")
            row.invoice_pdf_url=item.get("invoice_pdf")
    db.commit()
    return list(db.execute(select(BillingInvoice).where(BillingInvoice.workspace_id==workspace_id,BillingInvoice.provider==provider.provider_name).order_by(BillingInvoice.created_at.desc())).scalars().all())

def apply_stripe_event(db:Session,event:dict)->str:
    event_type=str(event["type"]); obj=event.get("data",{}).get("object",{})
    if not isinstance(obj,dict): return "ignored"
    metadata=obj.get("metadata") if isinstance(obj.get("metadata"),dict) else {}
    workspace_raw=metadata.get("workspace_id")
    workspace_id=None
    try:
        workspace_id=uuid.UUID(str(workspace_raw)) if workspace_raw else None
    except (ValueError,TypeError): workspace_id=None
    sub_id=obj.get("id") if event_type.startswith("customer.subscription.") else obj.get("subscription")
    if not isinstance(sub_id,str) and isinstance(obj.get("subscription"),dict):
        sub_id=obj["subscription"].get("id")
    if isinstance(sub_id,str):
        sub=db.execute(select(Subscription).where(Subscription.provider=="stripe",Subscription.provider_subscription_id==sub_id)).scalar_one_or_none()
        if sub is not None:
            raw_status=str(obj.get("status") or "")
            mapped={"trialing":"trialing","active":"active","past_due":"past_due","canceled":"canceled","incomplete_expired":"expired","unpaid":"past_due","paused":"past_due","incomplete":"past_due"}.get(raw_status)
            if mapped is not None and mapped in ("trialing","active","past_due","canceled","expired"):
                sub.status=mapped
            if "cancel_at_period_end" in obj: sub.cancel_at_period_end=bool(obj.get("cancel_at_period_end"))
            if "current_period_start" in obj: sub.current_period_start=__import__("datetime").datetime.fromtimestamp(int(obj["current_period_start"]),tz=__import__("datetime").UTC) if obj.get("current_period_start") else None
            if "current_period_end" in obj: sub.current_period_end=__import__("datetime").datetime.fromtimestamp(int(obj["current_period_end"]),tz=__import__("datetime").UTC) if obj.get("current_period_end") else None
    if event_type=="checkout.session.completed" and isinstance(obj.get("subscription"),str):
        if workspace_id is None: workspace_raw=obj.get("client_reference_id"); 
        try: workspace_id=workspace_id or uuid.UUID(str(workspace_raw))
        except (ValueError,TypeError): pass
        if workspace_id:
            sub=db.execute(select(Subscription).where(Subscription.workspace_id==workspace_id)).order_by(Subscription.created_at.desc()).limit(1).scalar_one_or_none()
            if sub:
                sub.provider="stripe"; sub.provider_customer_id=str(obj.get("customer")) if obj.get("customer") else sub.provider_customer_id; sub.provider_subscription_id=str(obj["subscription"]); sub.status="active"
    if workspace_id and event_type.startswith("invoice."):
        invoice_id=obj.get("id")
        if isinstance(invoice_id,str):
            row=db.execute(select(BillingInvoice).where(BillingInvoice.provider=="stripe",BillingInvoice.provider_invoice_id==invoice_id)).scalar_one_or_none()
            if row is None:
                row=BillingInvoice(workspace_id=workspace_id,provider="stripe",provider_invoice_id=invoice_id,status=str(obj.get("status") or event_type.split(".")[-1]),currency=str(obj.get("currency") or "usd"),amount_due=Decimal(int(obj.get("amount_due") or 0))/Decimal(100),amount_paid=Decimal(int(obj.get("amount_paid") or 0))/Decimal(100),hosted_invoice_url=obj.get("hosted_invoice_url"),invoice_pdf_url=obj.get("invoice_pdf"),provider_metadata={"livemode":bool(obj.get("livemode",False))})
                db.add(row)
            else:
                row.status=str(obj.get("status") or row.status)
            if event_type=="invoice.payment_failed":
                sub=db.execute(select(Subscription).where(Subscription.workspace_id==workspace_id,Subscription.status.in_(("trialing","active","past_due")))).order_by(Subscription.created_at.desc()).limit(1).scalar_one_or_none()
                if sub: sub.status="past_due"
    db.flush()
    return event_type
