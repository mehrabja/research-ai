"""M37 Phase 2-I — transaction rollback safety for M37 workflows."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, func, select

from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.db.models.user import User
from app.db.session import SessionLocal
from app.services import memberships as memberships_service
from app.services import reports as reports_service
from app.services import workspaces as workspaces_service
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
                email=f"txn-{uid.hex[:8]}@e.com",
                password_hash="x",
            )
        )
        db.commit()
    uids.append(uid)
    return uid


def test_workspace_creation_rolls_back_on_subscription_failure(
    cleanup_users: list[uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uid = _mk_user(cleanup_users)

    def _boom(*_a, **_kw):
        raise RuntimeError("simulated subscription failure")

    monkeypatch.setattr(
        workspaces_service,
        "Subscription",
        _boom,
        raising=False,
    )
    # The actual call site uses Subscription(...) — patch the model.
    import app.db.models.subscription as sub_mod

    monkeypatch.setattr(sub_mod, "Subscription", _boom)

    with SessionLocal() as db, pytest.raises(RuntimeError):
        workspaces_service.create_workspace(
            db, name="txn-ws", owner_user_id=uid
        )

    with SessionLocal() as db:
        from app.db.models.workspace import Workspace

        n = db.execute(
            select(func.count())
            .select_from(Workspace)
            .where(Workspace.owner_user_id == uid)
        ).scalar_one()
    assert n == 0


def test_create_report_rolls_back_on_usage_failure(
    cleanup_users: list[uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uid = _mk_user(cleanup_users)

    def _boom(*_a, **_kw):
        raise RuntimeError("simulated usage failure")

    monkeypatch.setattr(
        reports_service.usage_service, "record_event", _boom
    )

    with SessionLocal() as db, pytest.raises(RuntimeError):
        reports_service.create_report(
            db,
            user_id=uid,
            data={"topic": "x", "output_language": "en"},
        )

    with SessionLocal() as db:
        n = db.execute(
            select(func.count())
            .select_from(Report)
            .where(Report.user_id == uid)
        ).scalar_one()
    assert n == 0


def test_role_change_rolls_back_on_audit_failure(
    cleanup_users: list[uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _mk_user(cleanup_users)
    member = _mk_user(cleanup_users)

    with SessionLocal() as db:
        ws = workspaces_service.ensure_default_workspace(
            db, user_id=owner
        )
        db.commit()
        wid = ws.id

    # pro plan so we can add a member
    from app.db.models.plan import Plan
    from app.db.models.subscription import Subscription

    with SessionLocal() as db:
        pro = db.execute(
            select(Plan).where(Plan.code == "pro")
        ).scalar_one()
        sub = db.execute(
            select(Subscription).where(
                Subscription.workspace_id == wid
            )
        ).scalar_one()
        sub.plan_id = pro.id
        db.commit()

    with SessionLocal() as db:
        memberships_service.add_or_reactivate_member(
            db, workspace_id=wid, user_id=member, role="member"
        )
        db.commit()

    # Force audit to raise mid-transaction.
    def _boom(*_a, **_kw):
        raise RuntimeError("simulated audit failure")

    monkeypatch.setattr(
        memberships_service, "emit_audit", _boom
    )

    with SessionLocal() as db, pytest.raises(RuntimeError):
        memberships_service.change_member_role(
            db,
            workspace_id=wid,
            actor_user_id=owner,
            target_user_id=member,
            new_role="admin",
        )
        # No commit — we want to observe the unflushed state
        # actually, flush happens inside; the exception bubbles
        # before the caller commits, so any flush is rolled back.
        db.rollback()

    # Verify the role did not persist.
    with SessionLocal() as db:
        m = memberships_service.get_membership(
            db, workspace_id=wid, user_id=member
        )
        assert m is not None
        assert m.role == "member"


def test_quota_denial_does_not_create_partial_state(
    cleanup_users: list[uuid.UUID],
) -> None:
    """When reports.monthly is exhausted, no Report row is inserted."""
    uid = _mk_user(cleanup_users)

    # Fill the free quota (30 reports).
    with SessionLocal() as db:
        ws = workspaces_service.ensure_default_workspace(
            db, user_id=uid
        )
        db.commit()
        wid = ws.id

    from app.services import entitlements as ent

    with SessionLocal() as db:
        plan = ent.resolve_active_plan(db, workspace_id=wid)
        assert plan is not None
        limit = ent.get_limit(
            db, plan_id=plan.id, feature="reports.monthly"
        )
        assert limit == 30

    for i in range(limit):
        with SessionLocal() as db:
            reports_service.create_report(
                db,
                user_id=uid,
                data={"topic": f"r{i}", "output_language": "en"},
            )

    from app.core.exceptions import QuotaExceeded

    with SessionLocal() as db, pytest.raises(QuotaExceeded):
        reports_service.create_report(
            db,
            user_id=uid,
            data={"topic": "overflow", "output_language": "en"},
        )

    with SessionLocal() as db:
        n = db.execute(
            select(func.count())
            .select_from(Report)
            .where(Report.user_id == uid)
        ).scalar_one()
    assert n == limit
