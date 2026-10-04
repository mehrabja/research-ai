"""M37 Phase 2-F — billing abstraction tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.billing.fake import FakeBillingProvider
from app.db.models.plan import Plan
from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.db.models.user import User
from app.db.session import SessionLocal
from app.services import billing as billing_service
from app.services.workspaces import ensure_default_workspace
from tests._m37_cleanup import purge_test_users


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    uids: list[uuid.UUID] = []
    yield uids
    if not uids:
        return
    with SessionLocal() as db:
        pids = select(Project.id).where(Project.user_id.in_(uids))
        db.execute(
            delete(ProjectEvent).where(
                ProjectEvent.project_id.in_(pids)
            )
        )
        db.execute(delete(Report).where(Report.user_id.in_(uids)))
        db.execute(delete(Project).where(Project.user_id.in_(uids)))
        purge_test_users(db, uids)
        db.commit()


def _mk_user(uids: list[uuid.UUID]) -> uuid.UUID:
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(
            User(
                id=uid,
                email=f"b-{uid.hex[:8]}@e.com",
                password_hash="x",
            )
        )
        db.commit()
    uids.append(uid)
    return uid


def _ws_for(uid: uuid.UUID) -> uuid.UUID:
    with SessionLocal() as db:
        ws = ensure_default_workspace(db, user_id=uid)
        db.commit()
        return ws.id


# --- provider interface ---------------------------------------------------

def test_fake_provider_is_deterministic_and_idempotent() -> None:
    p = FakeBillingProvider()
    wid = uuid.uuid4()
    uid = uuid.uuid4()
    c1 = p.create_customer(
        workspace_id=wid, owner_user_id=uid, idempotency_key="c1"
    )
    c2 = p.create_customer(
        workspace_id=wid, owner_user_id=uid, idempotency_key="c1"
    )
    assert c1 == c2

    s1 = p.create_subscription(
        customer_id=c1, plan_code="pro", idempotency_key="s1"
    )
    s2 = p.create_subscription(
        customer_id=c1, plan_code="pro", idempotency_key="s1"
    )
    assert s1 == s2
    assert p.get_subscription(subscription_id=s1) is not None

    p.cancel_subscription(subscription_id=s1)
    assert (
        p.get_subscription(subscription_id=s1)["cancel_at_period_end"]
        is True
    )
    p.resume_subscription(subscription_id=s1)
    assert (
        p.get_subscription(subscription_id=s1)["cancel_at_period_end"]
        is False
    )


# --- change_plan ----------------------------------------------------------

def test_owner_can_change_plan(cleanup_users: list[uuid.UUID]) -> None:
    uid = _mk_user(cleanup_users)
    ws = _ws_for(uid)
    with SessionLocal() as db:
        pro = db.execute(
            select(Plan).where(Plan.code == "pro")
        ).scalar_one()
        sub = billing_service.change_plan(
            db,
            workspace_id=ws,
            actor_user_id=uid,
            new_plan_id=pro.id,
        )
        db.commit()
        assert sub.plan_id == pro.id


def test_non_owner_cannot_change_plan(
    cleanup_users: list[uuid.UUID],
) -> None:
    from app.core.exceptions import InsufficientRole
    from app.services import memberships as ms

    owner = _mk_user(cleanup_users)
    member = _mk_user(cleanup_users)
    ws = _ws_for(owner)

    # upgrade to pro first so member quota allows adding member
    with SessionLocal() as db:
        pro = db.execute(
            select(Plan).where(Plan.code == "pro")
        ).scalar_one()
        billing_service.change_plan(
            db, workspace_id=ws, actor_user_id=owner, new_plan_id=pro.id
        )
        db.commit()

    with SessionLocal() as db:
        ms.add_or_reactivate_member(
            db, workspace_id=ws, user_id=member, role="member"
        )
        db.commit()

    with SessionLocal() as db, pytest.raises(InsufficientRole):
        free = db.execute(
            select(Plan).where(Plan.code == "free")
        ).scalar_one()
        billing_service.change_plan(
            db,
            workspace_id=ws,
            actor_user_id=member,
            new_plan_id=free.id,
        )


# --- cancel / resume ------------------------------------------------------

def test_cancel_sets_flag(cleanup_users: list[uuid.UUID]) -> None:
    uid = _mk_user(cleanup_users)
    ws = _ws_for(uid)
    with SessionLocal() as db:
        sub = billing_service.cancel_subscription(
            db, workspace_id=ws, actor_user_id=uid
        )
        db.commit()
        assert sub.cancel_at_period_end is True
    with SessionLocal() as db:
        sub = billing_service.resume_subscription(
            db, workspace_id=ws, actor_user_id=uid
        )
        db.commit()
        assert sub.cancel_at_period_end is False


# --- billing event idempotency -------------------------------------------

def test_billing_event_idempotent(
    cleanup_users: list[uuid.UUID],
) -> None:
    """Each run uses a fresh provider_event_id so the test is
    independent of any pre-existing rows in the DB."""
    event_id = f"evt-{uuid.uuid4().hex}"
    with SessionLocal() as db:
        e1, c1 = billing_service.record_billing_event(
            db,
            provider="fake",
            provider_event_id=event_id,
            event_type="invoice.paid",
            payload_hash="a" * 64,
        )
        db.commit()
        e2, c2 = billing_service.record_billing_event(
            db,
            provider="fake",
            provider_event_id=event_id,
            event_type="invoice.paid",
            payload_hash="a" * 64,
        )
        db.commit()
        assert c1 is True
        assert c2 is False
        assert e1.id == e2.id


class _TrackingBillingProvider:
    provider_name = "stripe"

    def __init__(self):
        self.calls = []

    def price_id_for_plan(self, **kwargs):
        self.calls.append(("price", kwargs))
        return f"price_{kwargs['plan_code']}"

    def change_subscription_plan(self, **kwargs):
        self.calls.append(("change_plan", kwargs))

    def cancel_subscription(self, **kwargs):
        self.calls.append(("cancel", kwargs))

    def resume_subscription(self, **kwargs):
        self.calls.append(("resume", kwargs))


def test_cancel_and_resume_call_provider_when_provider_backed(cleanup_users):
    uid = _mk_user(cleanup_users)
    ws = _ws_for(uid)
    provider = _TrackingBillingProvider()
    with SessionLocal() as db:
        sub = billing_service.require_live_subscription(db, workspace_id=ws)
        sub.provider = "stripe"
        sub.provider_subscription_id = "sub_123"
        db.commit()

    with SessionLocal() as db:
        billing_service.cancel_subscription(
            db, workspace_id=ws, actor_user_id=uid, provider=provider
        )
        db.commit()
    assert provider.calls[0][0] == "cancel"
    assert provider.calls[0][1]["subscription_id"] == "sub_123"
    assert provider.calls[0][1]["idempotency_key"] == f"cancel-subscription:{sub.id}"

    with SessionLocal() as db:
        billing_service.resume_subscription(
            db, workspace_id=ws, actor_user_id=uid, provider=provider
        )
        db.commit()
    assert provider.calls[1][0] == "resume"
    assert provider.calls[1][1]["subscription_id"] == "sub_123"
    assert provider.calls[1][1]["idempotency_key"] == f"resume-subscription:{sub.id}"


def test_provider_backed_plan_change_calls_provider(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)
    ws = _ws_for(uid)
    provider = _TrackingBillingProvider()
    with SessionLocal() as db:
        sub = billing_service.require_live_subscription(db, workspace_id=ws)
        sub.provider = "stripe"
        sub.provider_subscription_id = "sub_456"
        db.commit()

    with SessionLocal() as db:
        pro = db.execute(
            select(Plan).where(Plan.code == "pro")
        ).scalar_one()
        sub = billing_service.change_plan(
            db,
            workspace_id=ws,
            actor_user_id=uid,
            new_plan_id=pro.id,
            provider=provider,
        )
        db.commit()

    assert sub.plan_id == pro.id
    assert provider.calls[0][0] == "price"
    assert provider.calls[1][0] == "change_plan"
    assert provider.calls[1][1]["subscription_id"] == "sub_456"
    assert provider.calls[1][1]["price_id"] == "price_pro"
    assert provider.calls[1][1]["idempotency_key"] == f"plan-change:{sub.id}:{pro.id}"
