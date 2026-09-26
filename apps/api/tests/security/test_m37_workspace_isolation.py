"""M37 Phase 2-H — workspace tenant isolation.

Every M37 route that accepts ``workspace_id`` must return 404 (not
403) for a caller who has no active membership on that workspace.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.db.session import SessionLocal
from tests._m37_api_helpers import auth, client, create_workspace
from tests._m37_api_helpers import register_and_login as _reg
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


def test_get_foreign_workspace_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    ua, ta = _reg()
    ub, tb = _reg()
    cleanup_users.extend([ua, ub])
    wid_a = create_workspace(ta, "a-only")

    r = client.get(
        f"/api/v1/workspaces/{wid_a}", headers=auth(tb)
    )
    assert r.status_code == 404


def test_patch_foreign_workspace_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    ua, ta = _reg()
    ub, tb = _reg()
    cleanup_users.extend([ua, ub])
    wid_a = create_workspace(ta, "a-only")

    r = client.patch(
        f"/api/v1/workspaces/{wid_a}",
        headers=auth(tb),
        json={"name": "hijacked"},
    )
    assert r.status_code == 404

    # Owner still sees original name.
    r = client.get(
        f"/api/v1/workspaces/{wid_a}", headers=auth(ta)
    )
    assert r.status_code == 200
    assert r.json()["name"] == "a-only"


def test_list_foreign_members_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    ua, ta = _reg()
    ub, tb = _reg()
    cleanup_users.extend([ua, ub])
    wid_a = create_workspace(ta, "a-only")

    r = client.get(
        f"/api/v1/workspaces/{wid_a}/members",
        headers=auth(tb),
    )
    assert r.status_code == 404


def test_patch_foreign_member_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    ua, ta = _reg()
    ub, tb = _reg()
    cleanup_users.extend([ua, ub])
    wid_a = create_workspace(ta, "a-only")

    r = client.patch(
        f"/api/v1/workspaces/{wid_a}/members/{ua}",
        headers=auth(tb),
        json={"role": "admin"},
    )
    assert r.status_code == 404


def test_delete_foreign_member_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    ua, ta = _reg()
    ub, tb = _reg()
    cleanup_users.extend([ua, ub])
    wid_a = create_workspace(ta, "a-only")

    r = client.delete(
        f"/api/v1/workspaces/{wid_a}/members/{ua}",
        headers=auth(tb),
    )
    assert r.status_code == 404


def test_create_foreign_invitation_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    ua, ta = _reg()
    ub, tb = _reg()
    cleanup_users.extend([ua, ub])
    wid_a = create_workspace(ta, "a-only")

    r = client.post(
        f"/api/v1/workspaces/{wid_a}/members/invitations",
        headers=auth(tb),
        json={"email": "x@example.com", "role": "member"},
    )
    assert r.status_code == 404


def test_get_foreign_usage_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    ua, ta = _reg()
    ub, tb = _reg()
    cleanup_users.extend([ua, ub])
    wid_a = create_workspace(ta, "a-only")

    r = client.get(
        f"/api/v1/workspaces/{wid_a}/usage", headers=auth(tb)
    )
    assert r.status_code == 404


def test_get_foreign_plan_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    ua, ta = _reg()
    ub, tb = _reg()
    cleanup_users.extend([ua, ub])
    wid_a = create_workspace(ta, "a-only")

    r = client.get(
        f"/api/v1/workspaces/{wid_a}/plan", headers=auth(tb)
    )
    assert r.status_code == 404


def test_get_foreign_subscription_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    ua, ta = _reg()
    ub, tb = _reg()
    cleanup_users.extend([ua, ub])
    wid_a = create_workspace(ta, "a-only")

    r = client.get(
        f"/api/v1/workspaces/{wid_a}/subscription",
        headers=auth(tb),
    )
    assert r.status_code == 404


def test_guessed_uuid_does_not_bypass(
    cleanup_users: list[uuid.UUID],
) -> None:
    ua, ta = _reg()
    cleanup_users.append(ua)

    for path in (
        "",
        "/members",
        "/usage",
        "/plan",
        "/subscription",
    ):
        r = client.get(
            f"/api/v1/workspaces/{uuid.uuid4()}{path}",
            headers=auth(ta),
        )
        assert r.status_code == 404, path


def test_unauthenticated_request_rejected(
    cleanup_users: list[uuid.UUID],
) -> None:
    ua, ta = _reg()
    cleanup_users.append(ua)
    wid_a = create_workspace(ta, "a-only")

    r = client.get(f"/api/v1/workspaces/{wid_a}")
    assert r.status_code in (401, 403)
