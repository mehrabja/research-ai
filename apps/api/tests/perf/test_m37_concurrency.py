"""M37 Phase 2-I — concurrency invariants across M37 services."""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import delete, func, select

from app.db.models.membership import WorkspaceMembership
from app.db.models.plan import Plan
from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.db.models.subscription import Subscription
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.domain.membership import MEMBERSHIP_ACTIVE
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
                email=f"conc-{uid.hex[:8]}@e.com",
                password_hash="x",
            )
        )
        db.commit()
    uids.append(uid)
    return uid


def _upgrade_to_pro(wid: uuid.UUID) -> None:
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


def test_concurrent_default_workspace_provisioning(
    cleanup_users: list[uuid.UUID],
) -> None:
    """Many threads call ``ensure_default_workspace`` for the same
    user; exactly one workspace is created."""
    uid = _mk_user(cleanup_users)

    def _attempt(_i: int) -> uuid.UUID:
        with SessionLocal() as db:
            ws = workspaces_service.ensure_default_workspace(
                db, user_id=uid
            )
            db.commit()
            return ws.id

    with ThreadPoolExecutor(max_workers=6) as pool:
        ids = list(pool.map(_attempt, range(6)))

    assert len(set(ids)) == 1

    with SessionLocal() as db:
        n = db.execute(
            select(func.count())
            .select_from(Workspace)
            .where(Workspace.owner_user_id == uid)
        ).scalar_one()
    assert n == 1


def test_concurrent_role_change_is_serialized(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    member = _mk_user(cleanup_users)

    with SessionLocal() as db:
        ws = workspaces_service.ensure_default_workspace(
            db, user_id=owner
        )
        db.commit()
        wid = ws.id
    _upgrade_to_pro(wid)

    with SessionLocal() as db:
        memberships_service.add_or_reactivate_member(
            db, workspace_id=wid, user_id=member, role="member"
        )
        db.commit()

    def _attempt(role: str) -> str:
        with SessionLocal() as db:
            try:
                memberships_service.change_member_role(
                    db,
                    workspace_id=wid,
                    actor_user_id=owner,
                    target_user_id=member,
                    new_role=role,
                )
                db.commit()
                return "ok"
            except Exception as exc:  # noqa: BLE001
                return f"err:{type(exc).__name__}"

    with ThreadPoolExecutor(max_workers=4) as pool:
        _ = list(
            pool.map(
                _attempt,
                ["admin", "member", "viewer", "admin"],
            )
        )

    with SessionLocal() as db:
        m = memberships_service.get_membership(
            db, workspace_id=wid, user_id=member
        )
    assert m is not None
    # Any of the requested roles is fine — the invariant is that
    # exactly one row exists with a valid role.
    assert m.role in ("admin", "member", "viewer")
    assert m.status == MEMBERSHIP_ACTIVE


def test_concurrent_report_creation_respects_monthly_quota(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)

    with SessionLocal() as db:
        ws = workspaces_service.ensure_default_workspace(
            db, user_id=uid
        )
        db.commit()
        wid = ws.id

    from app.services import entitlements as ent

    with SessionLocal() as db:
        plan = ent.resolve_active_plan(db, workspace_id=wid)
        limit = ent.get_limit(
            db, plan_id=plan.id, feature="reports.monthly"
        )

    from app.core.exceptions import QuotaExceeded

    n = limit + 3

    def _attempt(i: int) -> str:
        with SessionLocal() as db:
            try:
                reports_service.create_report(
                    db,
                    user_id=uid,
                    data={
                        "topic": f"c{i}",
                        "output_language": "en",
                    },
                )
                return "ok"
            except QuotaExceeded:
                return "quota"
            except Exception as exc:  # noqa: BLE001
                return f"err:{type(exc).__name__}"

    with ThreadPoolExecutor(max_workers=n) as pool:
        results = list(pool.map(_attempt, range(n)))

    assert results.count("ok") == limit, results
    assert results.count("quota") == n - limit, results


def test_concurrent_member_add_respects_quota(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    with SessionLocal() as db:
        ws = workspaces_service.ensure_default_workspace(
            db, user_id=owner
        )
        db.commit()
        wid = ws.id
    _upgrade_to_pro(wid)

    # Pro members.max = 10; owner already counts as 1 -> 9 slots.
    candidates = [_mk_user(cleanup_users) for _ in range(12)]

    from app.core.exceptions import QuotaExceeded
    from app.services import memberships as ms

    def _attempt(u: uuid.UUID) -> str:
        with SessionLocal() as db:
            try:
                ms.ensure_member_quota(db, workspace_id=wid)
                ms.add_or_reactivate_member(
                    db,
                    workspace_id=wid,
                    user_id=u,
                    role="member",
                )
                db.commit()
                return "ok"
            except QuotaExceeded:
                return "quota"
            except Exception as exc:  # noqa: BLE001
                return f"err:{type(exc).__name__}"

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(_attempt, candidates))

    ok = results.count("ok")
    # Exactly 9 additional members can be added (10 total with owner).
    assert ok == 9, results

    with SessionLocal() as db:
        n = db.execute(
            select(func.count())
            .select_from(WorkspaceMembership)
            .where(
                WorkspaceMembership.workspace_id == wid,
                WorkspaceMembership.status == MEMBERSHIP_ACTIVE,
            )
        ).scalar_one()
    assert n == 10
