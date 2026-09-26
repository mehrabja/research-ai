"""M37 — InvitationService tests.

Covers: creation, role gating, token security, single-use,
expiration, revocation, email match, member quota, concurrency.

Plan note
---------
Free plan has ``members.max = 1`` (owner only), so any test that
accepts an invitation or seeds an additional member must first lift
the workspace onto the ``pro`` plan (``members.max = 10``).
``test_accept_rejected_when_members_max_exceeded`` is the only test
that intentionally stays on the free plan.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.core.exceptions import (
    InsufficientRole,
    InvitationAlreadyAccepted,
    InvitationEmailMismatch,
    InvitationExpired,
    InvitationNotFound,
    InvitationRevoked,
    InvitationRoleInvalid,
    QuotaExceeded,
)
from app.db.models.invitation import WorkspaceInvitation
from app.db.models.membership import WorkspaceMembership
from app.db.models.plan import Plan
from app.db.models.project import Project, ProjectEvent
from app.db.models.subscription import Subscription
from app.db.models.user import User
from app.db.session import SessionLocal
from app.domain.invitation import INVITATION_PENDING, hash_token
from app.domain.membership import (
    MEMBERSHIP_ACTIVE,
    ROLE_ADMIN,
    ROLE_MEMBER,
    ROLE_OWNER,
    ROLE_VIEWER,
)
from app.services import invitations as invitations_service
from app.services import memberships as memberships_service
from app.services.workspaces import ensure_default_workspace
from tests._m37_cleanup import purge_test_users

# ==========================================================================
# Fixtures & helpers
# ==========================================================================

@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    uids: list[uuid.UUID] = []
    yield uids
    if not uids:
        return
    with SessionLocal() as db:
        pids = select(Project.id).where(Project.user_id.in_(uids))
        db.execute(
            delete(ProjectEvent).where(ProjectEvent.project_id.in_(pids))
        )
        db.execute(delete(Project).where(Project.user_id.in_(uids)))
        # workspaces / memberships / invitations / subscriptions
        # cascade from workspaces; helper purges owned workspaces.
        purge_test_users(db, uids)
        db.commit()


def _mk_user(
    uids: list[uuid.UUID], *, email: str | None = None
) -> uuid.UUID:
    uid = uuid.uuid4()
    if email is None:
        email = f"inv-{uid.hex[:8]}@example.com"
    with SessionLocal() as db:
        db.add(User(id=uid, email=email, password_hash="x"))
        db.commit()
    uids.append(uid)
    return uid


def _ws_for(uid: uuid.UUID) -> uuid.UUID:
    with SessionLocal() as db:
        ws = ensure_default_workspace(db, user_id=uid)
        db.commit()
        return ws.id


def _upgrade_to_pro(ws_id: uuid.UUID) -> None:
    """Swap the workspace's subscription to the ``pro`` plan.

    Default plan for new workspaces is ``free`` with
    ``members.max = 1`` (owner only).  Tests that add or accept a
    member must lift that limit first, since they exercise the
    invitation lifecycle, not the member quota.
    """
    with SessionLocal() as db:
        pro = db.execute(
            select(Plan).where(Plan.code == "pro")
        ).scalar_one()
        sub = db.execute(
            select(Subscription).where(
                Subscription.workspace_id == ws_id
            )
        ).scalar_one()
        sub.plan_id = pro.id
        db.commit()


# ==========================================================================
# create_invitation
# ==========================================================================

def test_owner_can_create_invitation(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)

    with SessionLocal() as db:
        inv, raw = invitations_service.create_invitation(
            db,
            workspace_id=ws_id,
            email="invitee@example.com",
            role=ROLE_MEMBER,
            invited_by_user_id=owner,
        )
        db.commit()
        assert inv.workspace_id == ws_id
        assert inv.email == "invitee@example.com"
        assert inv.role == ROLE_MEMBER
        # raw token is returned but hash is stored
        assert raw
        assert inv.token_hash != raw
        assert inv.token_hash == hash_token(raw)
        assert len(inv.token_hash) == 64


def test_invitation_rejects_owner_role(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    with SessionLocal() as db, pytest.raises(InvitationRoleInvalid):
        invitations_service.create_invitation(
            db,
            workspace_id=ws_id,
            email="x@example.com",
            role=ROLE_OWNER,  # not invitables
            invited_by_user_id=owner,
        )


def test_member_cannot_create_invitation(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    member = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)

    # Seed the member via direct service call
    with SessionLocal() as db:
        memberships_service.add_or_reactivate_member(
            db, workspace_id=ws_id, user_id=member, role=ROLE_MEMBER
        )
        db.commit()

    with SessionLocal() as db, pytest.raises(InsufficientRole):
        invitations_service.create_invitation(
            db,
            workspace_id=ws_id,
            email="x@example.com",
            role=ROLE_MEMBER,
            invited_by_user_id=member,
        )


def test_viewer_cannot_create_invitation(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    viewer = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)

    with SessionLocal() as db:
        memberships_service.add_or_reactivate_member(
            db, workspace_id=ws_id, user_id=viewer, role=ROLE_VIEWER
        )
        db.commit()

    with SessionLocal() as db, pytest.raises(InsufficientRole):
        invitations_service.create_invitation(
            db,
            workspace_id=ws_id,
            email="x@example.com",
            role=ROLE_MEMBER,
            invited_by_user_id=viewer,
        )


def test_admin_can_create_invitation(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    admin = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)

    with SessionLocal() as db:
        memberships_service.add_or_reactivate_member(
            db, workspace_id=ws_id, user_id=admin, role=ROLE_ADMIN
        )
        db.commit()

    with SessionLocal() as db:
        inv, _raw = invitations_service.create_invitation(
            db,
            workspace_id=ws_id,
            email="x@example.com",
            role=ROLE_MEMBER,
            invited_by_user_id=admin,
        )
        db.commit()
        assert inv.id is not None


def test_create_invitation_does_not_check_member_quota(
    cleanup_users: list[uuid.UUID],
) -> None:
    """Creating an invitation does NOT consume a member slot.

    Free plan has members.max = 1 (owner only), yet a pending
    invitation must be allowed.  Otherwise the owner could never
    invite anyone to a workspace that is about to be upgraded.
    """
    owner = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)  # stays on free plan

    with SessionLocal() as db:
        inv, _raw = invitations_service.create_invitation(
            db,
            workspace_id=ws_id,
            email="future-member@example.com",
            role=ROLE_MEMBER,
            invited_by_user_id=owner,
        )
        db.commit()
        assert inv.id is not None


# ==========================================================================
# accept_invitation
# ==========================================================================

def test_accept_creates_membership(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    invitee = _mk_user(
        cleanup_users, email="invitee-target@example.com"
    )
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)

    with SessionLocal() as db:
        inv, raw = invitations_service.create_invitation(
            db,
            workspace_id=ws_id,
            email="invitee-target@example.com",
            role=ROLE_MEMBER,
            invited_by_user_id=owner,
        )
        db.commit()
        inv_id = inv.id

    with SessionLocal() as db:
        m = invitations_service.accept_invitation(
            db, raw_token=raw, user_id=invitee
        )
        db.commit()
        assert m.workspace_id == ws_id
        assert m.user_id == invitee
        assert m.status == MEMBERSHIP_ACTIVE

    with SessionLocal() as db:
        row = db.get(WorkspaceInvitation, inv_id)
        assert row.accepted_at is not None


def test_accept_wrong_email_rejected(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    other = _mk_user(cleanup_users, email="other@example.com")
    ws_id = _ws_for(owner)

    with SessionLocal() as db:
        _inv, raw = invitations_service.create_invitation(
            db,
            workspace_id=ws_id,
            email="someone-else@example.com",
            role=ROLE_MEMBER,
            invited_by_user_id=owner,
        )
        db.commit()

    with SessionLocal() as db, pytest.raises(InvitationEmailMismatch):
        invitations_service.accept_invitation(
            db, raw_token=raw, user_id=other
        )


def test_accept_unknown_token_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    user = _mk_user(cleanup_users)
    with SessionLocal() as db, pytest.raises(InvitationNotFound):
        invitations_service.accept_invitation(
            db, raw_token="nope-not-a-token", user_id=user
        )


def test_accept_expired_rejected(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    invitee = _mk_user(
        cleanup_users, email="exp-target@example.com"
    )
    ws_id = _ws_for(owner)

    with SessionLocal() as db:
        inv, raw = invitations_service.create_invitation(
            db,
            workspace_id=ws_id,
            email="exp-target@example.com",
            role=ROLE_MEMBER,
            invited_by_user_id=owner,
        )
        # force expire
        inv.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()

    with SessionLocal() as db, pytest.raises(InvitationExpired):
        invitations_service.accept_invitation(
            db, raw_token=raw, user_id=invitee
        )


def test_accept_revoked_rejected(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    invitee = _mk_user(
        cleanup_users, email="rev-target@example.com"
    )
    ws_id = _ws_for(owner)

    with SessionLocal() as db:
        inv, raw = invitations_service.create_invitation(
            db,
            workspace_id=ws_id,
            email="rev-target@example.com",
            role=ROLE_MEMBER,
            invited_by_user_id=owner,
        )
        db.commit()
        inv_id = inv.id

    with SessionLocal() as db:
        invitations_service.revoke_invitation(
            db, invitation_id=inv_id, actor_user_id=owner
        )
        db.commit()

    with SessionLocal() as db, pytest.raises(InvitationRevoked):
        invitations_service.accept_invitation(
            db, raw_token=raw, user_id=invitee
        )


def test_accept_is_idempotent_for_same_user(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    invitee = _mk_user(
        cleanup_users, email="idem-target@example.com"
    )
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)

    with SessionLocal() as db:
        _inv, raw = invitations_service.create_invitation(
            db,
            workspace_id=ws_id,
            email="idem-target@example.com",
            role=ROLE_MEMBER,
            invited_by_user_id=owner,
        )
        db.commit()

    with SessionLocal() as db:
        m1 = invitations_service.accept_invitation(
            db, raw_token=raw, user_id=invitee
        )
        db.commit()

    with SessionLocal() as db:
        m2 = invitations_service.accept_invitation(
            db, raw_token=raw, user_id=invitee
        )
        db.commit()
        assert m1.id == m2.id

    # only one membership row for this user
    with SessionLocal() as db:
        rows = list(
            db.execute(
                select(WorkspaceMembership).where(
                    WorkspaceMembership.workspace_id == ws_id,
                    WorkspaceMembership.user_id == invitee,
                )
            ).scalars()
        )
        assert len(rows) == 1


def test_accept_concurrent_only_creates_one_membership(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    invitee = _mk_user(
        cleanup_users, email="conc-target@example.com"
    )
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)

    with SessionLocal() as db:
        _inv, raw = invitations_service.create_invitation(
            db,
            workspace_id=ws_id,
            email="conc-target@example.com",
            role=ROLE_MEMBER,
            invited_by_user_id=owner,
        )
        db.commit()

    def _attempt(_i: int) -> str:
        with SessionLocal() as db:
            try:
                invitations_service.accept_invitation(
                    db, raw_token=raw, user_id=invitee
                )
                db.commit()
                return "ok"
            except InvitationAlreadyAccepted:
                return "already"
            except Exception as exc:  # noqa: BLE001
                return f"err:{type(exc).__name__}"

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(_attempt, range(4)))

    assert results.count("ok") >= 1, results

    with SessionLocal() as db:
        rows = list(
            db.execute(
                select(WorkspaceMembership).where(
                    WorkspaceMembership.workspace_id == ws_id,
                    WorkspaceMembership.user_id == invitee,
                )
            ).scalars()
        )
        assert len(rows) == 1


# ==========================================================================
# quota (deliberately stays on free plan)
# ==========================================================================

def test_accept_rejected_when_members_max_exceeded(
    cleanup_users: list[uuid.UUID],
) -> None:
    """Free plan has members.max = 1 (owner only).

    This is the ONLY test that intentionally stays on the free plan
    so the quota rejection path is exercised end-to-end.
    """
    owner = _mk_user(cleanup_users)
    invitee = _mk_user(
        cleanup_users, email="quota-target@example.com"
    )
    ws_id = _ws_for(owner)  # stays on free plan

    with SessionLocal() as db:
        _inv, raw = invitations_service.create_invitation(
            db,
            workspace_id=ws_id,
            email="quota-target@example.com",
            role=ROLE_MEMBER,
            invited_by_user_id=owner,
        )
        db.commit()

    with SessionLocal() as db, pytest.raises(QuotaExceeded) as exc_info:
        invitations_service.accept_invitation(
            db, raw_token=raw, user_id=invitee
        )
    assert exc_info.value.feature == "members.max"


# ==========================================================================
# revoke_invitation
# ==========================================================================

def test_revoke_is_idempotent(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)

    with SessionLocal() as db:
        inv, _raw = invitations_service.create_invitation(
            db,
            workspace_id=ws_id,
            email="x@example.com",
            role=ROLE_MEMBER,
            invited_by_user_id=owner,
        )
        db.commit()
        inv_id = inv.id

    with SessionLocal() as db:
        invitations_service.revoke_invitation(
            db, invitation_id=inv_id, actor_user_id=owner
        )
        db.commit()

    with SessionLocal() as db:
        inv2 = invitations_service.revoke_invitation(
            db, invitation_id=inv_id, actor_user_id=owner
        )
        db.commit()
        assert inv2.revoked_at is not None


def test_revoke_accepted_invitation_rejected(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    invitee = _mk_user(
        cleanup_users, email="rev2-target@example.com"
    )
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)

    with SessionLocal() as db:
        inv, raw = invitations_service.create_invitation(
            db,
            workspace_id=ws_id,
            email="rev2-target@example.com",
            role=ROLE_MEMBER,
            invited_by_user_id=owner,
        )
        db.commit()
        inv_id = inv.id

    with SessionLocal() as db:
        invitations_service.accept_invitation(
            db, raw_token=raw, user_id=invitee
        )
        db.commit()

    with SessionLocal() as db, pytest.raises(InvitationAlreadyAccepted):
        invitations_service.revoke_invitation(
            db, invitation_id=inv_id, actor_user_id=owner
        )


# ==========================================================================
# list_invitations
# ==========================================================================

def test_list_returns_pending_invitations(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)

    with SessionLocal() as db:
        for i in range(3):
            invitations_service.create_invitation(
                db,
                workspace_id=ws_id,
                email=f"l-{i}@example.com",
                role=ROLE_MEMBER,
                invited_by_user_id=owner,
            )
        db.commit()

    with SessionLocal() as db:
        rows = invitations_service.list_invitations(
            db,
            workspace_id=ws_id,
            actor_user_id=owner,
            state=INVITATION_PENDING,
        )
        assert len(rows) == 3
