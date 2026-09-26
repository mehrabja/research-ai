"""M37 — shared helpers for cross-tenant / security tests.

All helpers are deterministic and idempotent-safe.  Cleanup is
expected to happen through ``tests._m37_cleanup.purge_test_users``.
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models.plan import Plan
from app.db.models.subscription import Subscription
from app.db.session import SessionLocal
from app.main import app

client = TestClient(app)

PW = "Correct Horse Battery Staple!"


def register_and_login(
    prefix: str = "m37sec",
) -> tuple[uuid.UUID, str]:
    email = f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PW},
    )
    assert r.status_code == 201, r.text
    uid = uuid.UUID(r.json()["id"])
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PW},
    )
    assert r.status_code == 200, r.text
    return uid, r.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_workspace(token: str, name: str = "W") -> str:
    r = client.post(
        "/api/v1/workspaces",
        headers=auth(token),
        json={"name": name},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def upgrade_to_pro(workspace_id: str) -> None:
    """Swap workspace subscription to pro (members.max = 10)."""
    with SessionLocal() as db:
        pro = db.execute(
            select(Plan).where(Plan.code == "pro")
        ).scalar_one()
        sub = db.execute(
            select(Subscription).where(
                Subscription.workspace_id == uuid.UUID(workspace_id)
            )
        ).scalar_one()
        sub.plan_id = pro.id
        db.commit()
