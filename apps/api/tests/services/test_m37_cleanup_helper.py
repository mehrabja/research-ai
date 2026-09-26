"""M37 — fixture cleanup helper regression tests.

Proves the centralized cleanup respects the workspace FK graph.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.models.membership import WorkspaceMembership
from app.db.models.plan import Plan
from app.db.models.subscription import Subscription
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.domain.billing import PROVIDER_NONE, SUB_ACTIVE
from app.domain.membership import MEMBERSHIP_ACTIVE, ROLE_OWNER
from app.domain.plan import DEFAULT_PLAN_CODE
from app.domain.workspace import WORKSPACE_STATUS_ACTIVE, slugify
from tests._m37_cleanup import purge_test_users


def _mk_user(db) -> uuid.UUID:
    uid = uuid.uuid4()
    db.add(
        User(
            id=uid,
            email=f"m37cl-{uid.hex[:8]}@e.com",
            password_hash="x",
        )
    )
    db.flush()
    return uid


def _mk_workspace(db, *, owner: uuid.UUID) -> Workspace:
    slug = f"{slugify('ws')}-{uuid.uuid4().hex[:6]}"
    ws = Workspace(
        name="ws",
        slug=slug,
        owner_user_id=owner,
        status=WORKSPACE_STATUS_ACTIVE,
    )
    db.add(ws)
    db.flush()
    db.add(
        WorkspaceMembership(
            workspace_id=ws.id,
            user_id=owner,
            role=ROLE_OWNER,
            status=MEMBERSHIP_ACTIVE,
        )
    )
    free = db.execute(
        select(Plan).where(Plan.code == DEFAULT_PLAN_CODE)
    ).scalar_one()
    db.add(
        Subscription(
            workspace_id=ws.id,
            plan_id=free.id,
            status=SUB_ACTIVE,
            provider=PROVIDER_NONE,
        )
    )
    db.flush()
    return ws


def test_cleanup_user_with_workspace_only() -> None:
    with SessionLocal() as db:
        uid = _mk_user(db)
        ws = _mk_workspace(db, owner=uid)
        db.commit()
        ws_id, uid_val = ws.id, uid

    with SessionLocal() as db:
        purge_test_users(db, [uid_val])
        db.commit()

    with SessionLocal() as db:
        assert db.get(User, uid_val) is None
        assert db.get(Workspace, ws_id) is None
        assert (
            db.execute(
                select(WorkspaceMembership).where(
                    WorkspaceMembership.workspace_id == ws_id
                )
            ).scalar_one_or_none()
            is None
        )
        assert (
            db.execute(
                select(Subscription).where(
                    Subscription.workspace_id == ws_id
                )
            ).scalar_one_or_none()
            is None
        )


def test_cleanup_leaves_other_users_untouched() -> None:
    with SessionLocal() as db:
        u1 = _mk_user(db)
        u2 = _mk_user(db)
        _mk_workspace(db, owner=u1)
        ws2 = _mk_workspace(db, owner=u2)
        db.commit()
        u2_val, ws2_val = u2, ws2.id

    with SessionLocal() as db:
        purge_test_users(db, [u1])
        db.commit()

    with SessionLocal() as db:
        assert db.get(User, u2_val) is not None
        assert db.get(Workspace, ws2_val) is not None


def test_cleanup_empty_is_noop() -> None:
    with SessionLocal() as db:
        purge_test_users(db, [])
        db.commit()
