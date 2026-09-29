"""M37 Phase 2-H — invitation token abuse."""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select, text

from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.db.session import SessionLocal
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


def _make_invitation(
    owner_token: str, wid: str, email: str
) -> tuple[str, str]:
    r = client.post(
        f"/api/v1/workspaces/{wid}/members/invitations",
        headers=auth(owner_token),
        json={"email": email, "role": "member"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return body["token"], body["invitation"]["id"]


def _register_email(email: str, cleanup: list[uuid.UUID]) -> str:
    pw = "Correct Horse Battery Staple!"
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": pw},
    )
    assert r.status_code == 201, r.text
    cleanup.append(uuid.UUID(r.json()["id"]))
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": pw},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_unknown_token_404(cleanup_users: list[uuid.UUID]) -> None:
    ua, ta = _reg()
    cleanup_users.append(ua)
    r = client.post(
        f"/api/v1/invitations/{uuid.uuid4().hex}/accept",
        headers=auth(ta),
    )
    assert r.status_code == 404


def test_wrong_email_403(cleanup_users: list[uuid.UUID]) -> None:
    ua, ta = _reg()
    ub, tb = _reg()
    cleanup_users.extend([ua, ub])
    wid = create_workspace(ta, "A")
    upgrade_to_pro(wid)
    token, _inv_id = _make_invitation(
        ta, wid, "someone-else@example.com"
    )
    r = client.post(
        f"/api/v1/invitations/{token}/accept", headers=auth(tb)
    )
    assert r.status_code == 403


def test_expired_410(cleanup_users: list[uuid.UUID]) -> None:
    ua, ta = _reg()
    cleanup_users.append(ua)
    wid = create_workspace(ta, "A")
    upgrade_to_pro(wid)
    invitee_email = f"exp-{uuid.uuid4().hex[:8]}@example.com"
    token, inv_id = _make_invitation(ta, wid, invitee_email)
    tb = _register_email(invitee_email, cleanup_users)

    # Force expiry.
    with SessionLocal() as db:
        db.execute(
            text(
                "UPDATE workspace_invitations "
                "SET expires_at = :t WHERE id = :id"
            ),
            {
                "t": datetime.now(UTC) - timedelta(minutes=1),
                "id": uuid.UUID(inv_id),
            },
        )
        db.commit()

    r = client.post(
        f"/api/v1/invitations/{token}/accept", headers=auth(tb)
    )
    assert r.status_code == 410


def test_revoked_410(cleanup_users: list[uuid.UUID]) -> None:
    ua, ta = _reg()
    cleanup_users.append(ua)
    wid = create_workspace(ta, "A")
    upgrade_to_pro(wid)
    invitee_email = f"rev-{uuid.uuid4().hex[:8]}@example.com"
    token, inv_id = _make_invitation(ta, wid, invitee_email)
    tb = _register_email(invitee_email, cleanup_users)

    with SessionLocal() as db:
        db.execute(
            text(
                "UPDATE workspace_invitations "
                "SET revoked_at = :t WHERE id = :id"
            ),
            {"t": datetime.now(UTC), "id": uuid.UUID(inv_id)},
        )
        db.commit()

    r = client.post(
        f"/api/v1/invitations/{token}/accept", headers=auth(tb)
    )
    assert r.status_code == 410


def test_double_accept_second_is_409_or_ok(
    cleanup_users: list[uuid.UUID],
) -> None:
    """After accepting, a second accept by the same user is idempotent
    (200 with the same membership).  A different user is rejected."""
    ua, ta = _reg()
    cleanup_users.append(ua)
    wid = create_workspace(ta, "A")
    upgrade_to_pro(wid)
    invitee_email = f"idem-{uuid.uuid4().hex[:8]}@example.com"
    token, _inv_id = _make_invitation(ta, wid, invitee_email)
    tb = _register_email(invitee_email, cleanup_users)

    r1 = client.post(
        f"/api/v1/invitations/{token}/accept", headers=auth(tb)
    )
    assert r1.status_code == 200

    r2 = client.post(
        f"/api/v1/invitations/{token}/accept", headers=auth(tb)
    )
    assert r2.status_code == 200
    assert r2.json()["user_id"] == r1.json()["user_id"]


def test_account_deletion_revokes_outstanding_invitation(
    cleanup_users: list[uuid.UUID],
) -> None:
    owner_id, owner_token = _reg()
    cleanup_users.append(owner_id)
    wid = create_workspace(owner_token, "Delete invitation")
    upgrade_to_pro(wid)
    _token, inv_id = _make_invitation(
        owner_token,
        wid,
        f"pending-{uuid.uuid4().hex[:8]}@example.com",
    )

    response = client.request(
        "DELETE",
        "/api/v1/auth/account",
        headers=auth(owner_token),
        json={"password": "Secret123456789"},
    )
    assert response.status_code == 200, response.text

    with SessionLocal() as db:
        row = db.execute(
            text(
                "SELECT accepted_at, revoked_at "
                "FROM workspace_invitations WHERE id = :id"
            ),
            {"id": uuid.UUID(inv_id)},
        ).one()
        assert row.accepted_at is None
        assert row.revoked_at is not None


def test_token_not_leaked_in_db(cleanup_users: list[uuid.UUID]) -> None:
    """Raw token must never appear in DB."""
    ua, ta = _reg()
    cleanup_users.append(ua)
    wid = create_workspace(ta, "A")
    token, _inv_id = _make_invitation(
        ta, wid, "leak-check@example.com"
    )
    assert token not in (wid)

    with SessionLocal() as db:
        rows = list(
            db.execute(
                text(
                    "SELECT token_hash FROM workspace_invitations "
                    "WHERE workspace_id = :w"
                ),
                {"w": uuid.UUID(wid)},
            ).all()
        )
    assert rows
    for (th,) in rows:
        assert th != token
        assert len(th) == 64  # sha256 hex
