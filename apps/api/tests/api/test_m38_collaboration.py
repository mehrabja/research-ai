"""M38 collaboration contract tests for invitations and ownership transfer."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.models.membership import WorkspaceMembership
from app.db.models.project import Project, ProjectEvent
from app.db.models.plan import Plan
from app.db.models.report import Report
from app.db.models.subscription import Subscription
from app.db.session import SessionLocal
from app.main import app
from tests._m37_cleanup import purge_test_users


client = TestClient(app)


def _reg(
    uids: list[uuid.UUID],
    prefix: str,
    email: str | None = None,
) -> tuple[uuid.UUID, str, str]:
    email = email or f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"
    password = "Correct Horse Battery Staple!"
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert r.status_code == 201, r.text
    uid = uuid.UUID(r.json()["id"])
    uids.append(uid)

    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return uid, r.json()["access_token"], email


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _workspace(token: str) -> uuid.UUID:
    r = client.post(
        "/api/v1/workspaces",
        headers=_auth(token),
        json={"name": "M38 Team"},
    )
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["id"])


def _upgrade_workspace_to_pro(workspace_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        plan = db.execute(
            select(Plan).where(Plan.code == "pro")
        ).scalar_one()
        subscription = db.execute(
            select(Subscription).where(
                Subscription.workspace_id == workspace_id,
                Subscription.status.in_((
                    "trialing",
                    "active",
                    "past_due",
                )),
            ).with_for_update()
        ).scalar_one()
        subscription.plan_id = plan.id
        db.commit()


def _cleanup_users(uids: list[uuid.UUID]) -> None:
    if not uids:
        return
    with SessionLocal() as db:
        pids = select(Project.id).where(Project.user_id.in_(uids))
        db.execute(delete(ProjectEvent).where(ProjectEvent.project_id.in_(pids)))
        db.execute(delete(Report).where(Report.user_id.in_(uids)))
        db.execute(delete(Project).where(Project.user_id.in_(uids)))
        purge_test_users(db, uids)
        db.commit()


def test_invitation_list_and_revoke() -> None:
    uids: list[uuid.UUID] = []
    try:
        _owner, owner_token, _ = _reg(uids, "m38-owner")
        workspace_id = _workspace(owner_token)
        invite_email = f"invitee-{uuid.uuid4().hex[:10]}@example.com"

        r = client.post(
            f"/api/v1/workspaces/{workspace_id}/members/invitations",
            headers=_auth(owner_token),
            json={"email": invite_email, "role": "member"},
        )
        assert r.status_code == 201, r.text
        invitation_id = r.json()["invitation"]["id"]

        r = client.get(
            f"/api/v1/workspaces/{workspace_id}/members/invitations",
            headers=_auth(owner_token),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["state"] == "pending"
        assert body["items"][0]["email"] == invite_email

        r = client.get(
            f"/api/v1/workspaces/{workspace_id}/members/invitations?state=pending",
            headers=_auth(owner_token),
        )
        assert r.status_code == 200
        assert r.json()["total"] == 1

        r = client.delete(
            f"/api/v1/workspaces/{workspace_id}/members/invitations/{invitation_id}",
            headers=_auth(owner_token),
        )
        assert r.status_code == 204, r.text

        r = client.get(
            f"/api/v1/workspaces/{workspace_id}/members/invitations?state=revoked",
            headers=_auth(owner_token),
        )
        assert r.status_code == 200, r.text
        assert r.json()["total"] == 1
        assert r.json()["items"][0]["state"] == "revoked"
    finally:
        _cleanup_users(uids)


def test_non_admin_cannot_revoke_invitation() -> None:
    uids: list[uuid.UUID] = []
    try:
        _owner, owner_token, _ = _reg(uids, "m38-owner")
        workspace_id = _workspace(owner_token)
        _upgrade_workspace_to_pro(workspace_id)

        member_email = f"member-{uuid.uuid4().hex[:10]}@example.com"
        r = client.post(
            f"/api/v1/workspaces/{workspace_id}/members/invitations",
            headers=_auth(owner_token),
            json={"email": member_email, "role": "member"},
        )
        assert r.status_code == 201, r.text
        member_invitation_token = r.json()["token"]

        _member, member_token, _ = _reg(uids, "m38-member", email=member_email)
        r = client.post(
            f"/api/v1/invitations/{member_invitation_token}/accept",
            headers=_auth(member_token),
        )
        assert r.status_code == 200, r.text

        other_email = f"other-{uuid.uuid4().hex[:10]}@example.com"
        r = client.post(
            f"/api/v1/workspaces/{workspace_id}/members/invitations",
            headers=_auth(owner_token),
            json={"email": other_email, "role": "viewer"},
        )
        assert r.status_code == 201, r.text
        other_invitation_id = r.json()["invitation"]["id"]

        r = client.delete(
            f"/api/v1/workspaces/{workspace_id}/members/invitations/{other_invitation_id}",
            headers=_auth(member_token),
        )
        assert r.status_code == 403, r.text
    finally:
        _cleanup_users(uids)


def test_invitation_list_hides_workspace_from_non_member() -> None:
    uids: list[uuid.UUID] = []
    try:
        _owner, owner_token, _ = _reg(uids, "m38-owner")
        workspace_id = _workspace(owner_token)
        _outsider, outsider_token, _ = _reg(uids, "m38-outsider")

        r = client.get(
            f"/api/v1/workspaces/{workspace_id}/members/invitations",
            headers=_auth(outsider_token),
        )
        assert r.status_code == 404, r.text
    finally:
        _cleanup_users(uids)


def test_transfer_ownership_updates_pointer_and_roles() -> None:
    uids: list[uuid.UUID] = []
    try:
        owner_id, owner_token, _ = _reg(uids, "m38-owner")
        target_email = f"target-{uuid.uuid4().hex[:10]}@example.com"
        target_id, target_token, _ = _reg(uids, "m38-target", email=target_email)

        workspace_id = _workspace(owner_token)
        _upgrade_workspace_to_pro(workspace_id)

        r = client.post(
            f"/api/v1/workspaces/{workspace_id}/members/invitations",
            headers=_auth(owner_token),
            json={"email": target_email, "role": "member"},
        )
        assert r.status_code == 201, r.text
        invitation_token = r.json()["token"]

        r = client.post(
            f"/api/v1/invitations/{invitation_token}/accept",
            headers=_auth(target_token),
        )
        assert r.status_code == 200, r.text

        r = client.post(
            f"/api/v1/workspaces/{workspace_id}/transfer-ownership",
            headers=_auth(owner_token),
            json={"target_user_id": str(target_id)},
        )
        assert r.status_code == 200, r.text
        assert r.json()["owner_user_id"] == str(target_id)

        r = client.get(
            f"/api/v1/workspaces/{workspace_id}",
            headers=_auth(owner_token),
        )
        assert r.status_code == 200, r.text
        assert r.json()["owner_user_id"] == str(target_id)

        with SessionLocal() as db:
            owner_membership = db.execute(
                select(WorkspaceMembership).where(
                    WorkspaceMembership.workspace_id == workspace_id,
                    WorkspaceMembership.user_id == owner_id,
                )
            ).scalar_one()
            target_membership = db.execute(
                select(WorkspaceMembership).where(
                    WorkspaceMembership.workspace_id == workspace_id,
                    WorkspaceMembership.user_id == target_id,
                )
            ).scalar_one()

            assert owner_membership.role == "admin"
            assert target_membership.role == "owner"

        r = client.post(
            f"/api/v1/workspaces/{workspace_id}/transfer-ownership",
            headers=_auth(owner_token),
            json={"target_user_id": str(owner_id)},
        )
        assert r.status_code == 403, r.text
    finally:
        _cleanup_users(uids)
