"""M37 Phase 2-E — Membership role / removal / ownership tests.

Covers:
  * change_member_role (owner, admin, member, viewer rules)
  * remove_member (soft removal + permissions)
  * transfer_ownership (atomicity, invariants, concurrency)
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import delete, select

from app.core.exceptions import (
    InsufficientRole,
    OwnerRoleImmutable,
    WorkspaceNotFound,
)
from app.db.models.membership import WorkspaceMembership
from app.db.models.plan import Plan
from app.db.models.project import Project, ProjectEvent
from app.db.models.subscription import Subscription
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.domain.membership import (
    MEMBERSHIP_ACTIVE,
    MEMBERSHIP_REMOVED,
    ROLE_ADMIN,
    ROLE_MEMBER,
    ROLE_OWNER,
    ROLE_VIEWER,
)
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
        purge_test_users(db, uids)
        db.commit()


def _mk_user(uids: list[uuid.UUID]) -> uuid.UUID:
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(
            User(
                id=uid,
                email=f"mem-{uid.hex[:8]}@example.com",
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


def _upgrade_to_pro(ws_id: uuid.UUID) -> None:
    """Lift members.max so extra members can be added in tests."""
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


def _add_member(
    ws_id: uuid.UUID, user_id: uuid.UUID, role: str
) -> None:
    with SessionLocal() as db:
        memberships_service.add_or_reactivate_member(
            db, workspace_id=ws_id, user_id=user_id, role=role
        )
        db.commit()


def _role(ws_id: uuid.UUID, user_id: uuid.UUID) -> str | None:
    with SessionLocal() as db:
        m = memberships_service.get_membership(
            db, workspace_id=ws_id, user_id=user_id
        )
        return None if m is None else m.role


def _status(ws_id: uuid.UUID, user_id: uuid.UUID) -> str | None:
    with SessionLocal() as db:
        m = memberships_service.get_membership(
            db, workspace_id=ws_id, user_id=user_id
        )
        return None if m is None else m.status


# ==========================================================================
# change_member_role
# ==========================================================================

def test_owner_promotes_member_to_admin(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    member = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)
    _add_member(ws_id, member, ROLE_MEMBER)

    with SessionLocal() as db:
        m = memberships_service.change_member_role(
            db,
            workspace_id=ws_id,
            actor_user_id=owner,
            target_user_id=member,
            new_role=ROLE_ADMIN,
        )
        db.commit()
        assert m.role == ROLE_ADMIN


def test_owner_demotes_admin_to_member(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    admin = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)
    _add_member(ws_id, admin, ROLE_ADMIN)

    with SessionLocal() as db:
        memberships_service.change_member_role(
            db,
            workspace_id=ws_id,
            actor_user_id=owner,
            target_user_id=admin,
            new_role=ROLE_MEMBER,
        )
        db.commit()
    assert _role(ws_id, admin) == ROLE_MEMBER


def test_change_role_to_owner_rejected(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    member = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)
    _add_member(ws_id, member, ROLE_MEMBER)

    with SessionLocal() as db, pytest.raises(OwnerRoleImmutable):
        memberships_service.change_member_role(
            db,
            workspace_id=ws_id,
            actor_user_id=owner,
            target_user_id=member,
            new_role=ROLE_OWNER,
        )


def test_owner_cannot_change_own_role(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)

    with SessionLocal() as db, pytest.raises(OwnerRoleImmutable):
        memberships_service.change_member_role(
            db,
            workspace_id=ws_id,
            actor_user_id=owner,
            target_user_id=owner,
            new_role=ROLE_ADMIN,
        )


def test_admin_cannot_promote_to_admin(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    admin = _mk_user(cleanup_users)
    member = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)
    _add_member(ws_id, admin, ROLE_ADMIN)
    _add_member(ws_id, member, ROLE_MEMBER)

    with SessionLocal() as db, pytest.raises(InsufficientRole):
        memberships_service.change_member_role(
            db,
            workspace_id=ws_id,
            actor_user_id=admin,
            target_user_id=member,
            new_role=ROLE_ADMIN,
        )


def test_admin_cannot_touch_other_admin(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    admin1 = _mk_user(cleanup_users)
    admin2 = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)
    _add_member(ws_id, admin1, ROLE_ADMIN)
    _add_member(ws_id, admin2, ROLE_ADMIN)

    with SessionLocal() as db, pytest.raises(InsufficientRole):
        memberships_service.change_member_role(
            db,
            workspace_id=ws_id,
            actor_user_id=admin1,
            target_user_id=admin2,
            new_role=ROLE_MEMBER,
        )


def test_member_cannot_change_roles(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    member1 = _mk_user(cleanup_users)
    member2 = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)
    _add_member(ws_id, member1, ROLE_MEMBER)
    _add_member(ws_id, member2, ROLE_MEMBER)

    with SessionLocal() as db, pytest.raises(InsufficientRole):
        memberships_service.change_member_role(
            db,
            workspace_id=ws_id,
            actor_user_id=member1,
            target_user_id=member2,
            new_role=ROLE_ADMIN,
        )


def test_viewer_cannot_change_roles(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    viewer = _mk_user(cleanup_users)
    member = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)
    _add_member(ws_id, viewer, ROLE_VIEWER)
    _add_member(ws_id, member, ROLE_MEMBER)

    with SessionLocal() as db, pytest.raises(InsufficientRole):
        memberships_service.change_member_role(
            db,
            workspace_id=ws_id,
            actor_user_id=viewer,
            target_user_id=member,
            new_role=ROLE_ADMIN,
        )


def test_same_role_is_idempotent(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    member = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)
    _add_member(ws_id, member, ROLE_MEMBER)

    with SessionLocal() as db:
        m = memberships_service.change_member_role(
            db,
            workspace_id=ws_id,
            actor_user_id=owner,
            target_user_id=member,
            new_role=ROLE_MEMBER,
        )
        db.commit()
        assert m.role == ROLE_MEMBER


# ==========================================================================
# remove_member
# ==========================================================================

def test_owner_removes_member(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    member = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)
    _add_member(ws_id, member, ROLE_MEMBER)

    with SessionLocal() as db:
        memberships_service.remove_member(
            db,
            workspace_id=ws_id,
            actor_user_id=owner,
            target_user_id=member,
        )
        db.commit()
    assert _status(ws_id, member) == MEMBERSHIP_REMOVED


def test_owner_removes_admin(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    admin = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)
    _add_member(ws_id, admin, ROLE_ADMIN)

    with SessionLocal() as db:
        memberships_service.remove_member(
            db,
            workspace_id=ws_id,
            actor_user_id=owner,
            target_user_id=admin,
        )
        db.commit()
    assert _status(ws_id, admin) == MEMBERSHIP_REMOVED


def test_admin_removes_member(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    admin = _mk_user(cleanup_users)
    member = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)
    _add_member(ws_id, admin, ROLE_ADMIN)
    _add_member(ws_id, member, ROLE_MEMBER)

    with SessionLocal() as db:
        memberships_service.remove_member(
            db,
            workspace_id=ws_id,
            actor_user_id=admin,
            target_user_id=member,
        )
        db.commit()
    assert _status(ws_id, member) == MEMBERSHIP_REMOVED


def test_admin_cannot_remove_other_admin(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    admin1 = _mk_user(cleanup_users)
    admin2 = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)
    _add_member(ws_id, admin1, ROLE_ADMIN)
    _add_member(ws_id, admin2, ROLE_ADMIN)

    with SessionLocal() as db, pytest.raises(InsufficientRole):
        memberships_service.remove_member(
            db,
            workspace_id=ws_id,
            actor_user_id=admin1,
            target_user_id=admin2,
        )


def test_admin_can_remove_self(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    admin = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)
    _add_member(ws_id, admin, ROLE_ADMIN)

    with SessionLocal() as db:
        memberships_service.remove_member(
            db,
            workspace_id=ws_id,
            actor_user_id=admin,
            target_user_id=admin,
        )
        db.commit()
    assert _status(ws_id, admin) == MEMBERSHIP_REMOVED


def test_owner_cannot_be_removed(
    cleanup_users: list[uuid.UUID],
) -> None:
    from app.core.exceptions import LastOwner

    owner = _mk_user(cleanup_users)
    admin = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)
    _add_member(ws_id, admin, ROLE_ADMIN)

    with SessionLocal() as db, pytest.raises(LastOwner):
        memberships_service.remove_member(
            db,
            workspace_id=ws_id,
            actor_user_id=admin,
            target_user_id=owner,
        )


def test_member_cannot_remove_others(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    member1 = _mk_user(cleanup_users)
    member2 = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)
    _add_member(ws_id, member1, ROLE_MEMBER)
    _add_member(ws_id, member2, ROLE_MEMBER)

    with SessionLocal() as db, pytest.raises(InsufficientRole):
        memberships_service.remove_member(
            db,
            workspace_id=ws_id,
            actor_user_id=member1,
            target_user_id=member2,
        )


def test_removed_member_can_be_reactivated(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    member = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)
    _add_member(ws_id, member, ROLE_MEMBER)

    with SessionLocal() as db:
        memberships_service.remove_member(
            db,
            workspace_id=ws_id,
            actor_user_id=owner,
            target_user_id=member,
        )
        db.commit()

    with SessionLocal() as db:
        m, created = memberships_service.add_or_reactivate_member(
            db, workspace_id=ws_id, user_id=member, role=ROLE_MEMBER
        )
        db.commit()
        assert created is True
        assert m.status == MEMBERSHIP_ACTIVE


# ==========================================================================
# transfer_ownership
# ==========================================================================

def test_transfer_ownership_to_admin(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    target = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)
    _add_member(ws_id, target, ROLE_ADMIN)

    with SessionLocal() as db:
        ws = memberships_service.transfer_ownership(
            db,
            workspace_id=ws_id,
            actor_user_id=owner,
            target_user_id=target,
        )
        db.commit()
        assert ws.owner_user_id == target

    assert _role(ws_id, owner) == ROLE_ADMIN
    assert _role(ws_id, target) == ROLE_OWNER


def test_transfer_ownership_to_member(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    target = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)
    _add_member(ws_id, target, ROLE_MEMBER)

    with SessionLocal() as db:
        memberships_service.transfer_ownership(
            db,
            workspace_id=ws_id,
            actor_user_id=owner,
            target_user_id=target,
        )
        db.commit()

    assert _role(ws_id, owner) == ROLE_ADMIN
    assert _role(ws_id, target) == ROLE_OWNER


def test_transfer_to_self_rejected(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)

    with SessionLocal() as db, pytest.raises(InsufficientRole):
        memberships_service.transfer_ownership(
            db,
            workspace_id=ws_id,
            actor_user_id=owner,
            target_user_id=owner,
        )


def test_transfer_by_non_owner_rejected(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    admin = _mk_user(cleanup_users)
    target = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)
    _add_member(ws_id, admin, ROLE_ADMIN)
    _add_member(ws_id, target, ROLE_MEMBER)

    with SessionLocal() as db, pytest.raises(InsufficientRole):
        memberships_service.transfer_ownership(
            db,
            workspace_id=ws_id,
            actor_user_id=admin,
            target_user_id=target,
        )


def test_transfer_to_non_member_rejected(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    outsider = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)

    with SessionLocal() as db, pytest.raises(WorkspaceNotFound):
        memberships_service.transfer_ownership(
            db,
            workspace_id=ws_id,
            actor_user_id=owner,
            target_user_id=outsider,
        )


def test_concurrent_transfer_only_one_succeeds(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner = _mk_user(cleanup_users)
    b = _mk_user(cleanup_users)
    c = _mk_user(cleanup_users)
    ws_id = _ws_for(owner)
    _upgrade_to_pro(ws_id)
    _add_member(ws_id, b, ROLE_MEMBER)
    _add_member(ws_id, c, ROLE_MEMBER)

    def _attempt(target: uuid.UUID) -> str:
        with SessionLocal() as db:
            try:
                memberships_service.transfer_ownership(
                    db,
                    workspace_id=ws_id,
                    actor_user_id=owner,
                    target_user_id=target,
                )
                db.commit()
                return "ok"
            except InsufficientRole:
                return "denied"
            except Exception as exc:  # noqa: BLE001
                return f"err:{type(exc).__name__}"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(_attempt, [b, c]))

    assert results.count("ok") == 1, results

    with SessionLocal() as db:
        ws = db.get(Workspace, ws_id)
        assert ws is not None
        assert ws.owner_user_id in (b, c)
        owners = list(
            db.execute(
                select(WorkspaceMembership).where(
                    WorkspaceMembership.workspace_id == ws_id,
                    WorkspaceMembership.role == ROLE_OWNER,
                    WorkspaceMembership.status == MEMBERSHIP_ACTIVE,
                )
            ).scalars()
        )
        assert len(owners) == 1
        assert owners[0].user_id == ws.owner_user_id
