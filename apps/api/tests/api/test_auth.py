"""Authentication API regression coverage."""
from __future__ import annotations

import uuid

from sqlalchemy import delete, select

from app.db.models.membership import WorkspaceMembership
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from tests._m37_api_helpers import PW, auth, client
from tests._m37_cleanup import purge_test_users


def test_register_with_workspace_persists_profile_and_workspace() -> None:
    email = f"auth-reg-{uuid.uuid4().hex[:12]}@example.com"
    workspace_name = "Regression Research Lab"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PW,
            "full_name": "Regression Researcher",
            "workspace_name": workspace_name,
        },
    )
    assert response.status_code == 201, response.text

    user_id = uuid.UUID(response.json()["id"])
    with SessionLocal() as db:
        user = db.get(User, user_id)
        assert user is not None
        assert user.full_name == "Regression Researcher"
        workspace = db.execute(
            select(Workspace)
            .join(
                WorkspaceMembership,
                WorkspaceMembership.workspace_id == Workspace.id,
            )
            .where(
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.role == "owner",
                WorkspaceMembership.status == "active",
                Workspace.name == workspace_name,
            )
        ).scalar_one_or_none()
        assert workspace is not None

        db.execute(
            delete(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace.id
            )
        )
        db.execute(delete(Workspace).where(Workspace.id == workspace.id))
        purge_test_users(db, [user_id])
        db.commit()


def test_login_roundtrip_returns_tokens() -> None:
    email = f"auth-login-{uuid.uuid4().hex[:12]}@example.com"
    register = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PW},
    )
    assert register.status_code == 201, register.text
    user_id = uuid.UUID(register.json()["id"])

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PW},
    )
    assert login.status_code == 200, login.text
    payload = login.json()
    assert isinstance(payload["access_token"], str)
    assert isinstance(payload["refresh_token"], str)

    response = client.get(
        "/api/v1/auth/me",
        headers=auth(payload["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["email"] == email

    with SessionLocal() as db:
        purge_test_users(db, [user_id])
        db.commit()
