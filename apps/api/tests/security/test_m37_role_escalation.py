"""M37 Phase 2-H — role escalation attempts."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.db.session import SessionLocal
from app.services import memberships as ms
from tests._m37_api_helpers import (
    auth,
    client,
    create_workspace,
    upgrade_to_pro,
)
from tests._m37_api_helpers import (
    register_and_login as _reg,
)
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


def _seed_member(
    wid: str, uid: uuid.UUID, role: str
) -> None:
    with SessionLocal() as db:
        ms.add_or_reactivate_member(
            db,
            workspace_id=uuid.UUID(wid),
            user_id=uid,
            role=role,
        )
        db.commit()


def test_member_cannot_self_promote(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner, to = _reg()
    member, tm = _reg()
    cleanup_users.extend([owner, member])
    wid = create_workspace(to, "A")
    upgrade_to_pro(wid)
    _seed_member(wid, member, "member")

    r = client.patch(
        f"/api/v1/workspaces/{wid}/members/{member}",
        headers=auth(tm),
        json={"role": "admin"},
    )
    assert r.status_code in (403, 404)


def test_member_cannot_make_self_owner(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner, to = _reg()
    member, tm = _reg()
    cleanup_users.extend([owner, member])
    wid = create_workspace(to, "A")
    upgrade_to_pro(wid)
    _seed_member(wid, member, "member")

    r = client.patch(
        f"/api/v1/workspaces/{wid}/members/{member}",
        headers=auth(tm),
        json={"role": "owner"},
    )
    # role=owner is not a valid MemberRoleUpdate literal -> 422
    assert r.status_code in (403, 404, 422)


def test_admin_cannot_create_admin(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner, to = _reg()
    admin, tadmin = _reg()
    member, _tm = _reg()
    cleanup_users.extend([owner, admin, member])
    wid = create_workspace(to, "A")
    upgrade_to_pro(wid)
    _seed_member(wid, admin, "admin")
    _seed_member(wid, member, "member")

    r = client.patch(
        f"/api/v1/workspaces/{wid}/members/{member}",
        headers=auth(tadmin),
        json={"role": "admin"},
    )
    assert r.status_code == 403


def test_admin_cannot_remove_owner(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner, to = _reg()
    admin, tadmin = _reg()
    cleanup_users.extend([owner, admin])
    wid = create_workspace(to, "A")
    upgrade_to_pro(wid)
    _seed_member(wid, admin, "admin")

    r = client.delete(
        f"/api/v1/workspaces/{wid}/members/{owner}",
        headers=auth(tadmin),
    )
    assert r.status_code == 409


def test_viewer_cannot_create_invitation(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner, to = _reg()
    viewer, tv = _reg()
    cleanup_users.extend([owner, viewer])
    wid = create_workspace(to, "A")
    upgrade_to_pro(wid)
    _seed_member(wid, viewer, "viewer")

    r = client.post(
        f"/api/v1/workspaces/{wid}/members/invitations",
        headers=auth(tv),
        json={"email": "x@example.com", "role": "member"},
    )
    assert r.status_code == 403


def test_member_cannot_create_invitation(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner, to = _reg()
    member, tm = _reg()
    cleanup_users.extend([owner, member])
    wid = create_workspace(to, "A")
    upgrade_to_pro(wid)
    _seed_member(wid, member, "member")

    r = client.post(
        f"/api/v1/workspaces/{wid}/members/invitations",
        headers=auth(tm),
        json={"email": "x@example.com", "role": "member"},
    )
    assert r.status_code == 403
