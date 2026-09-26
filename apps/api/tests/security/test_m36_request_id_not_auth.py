"""M36 — request ID is correlation only, never identity."""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _register_and_token() -> str:
    email = f"m36-rid-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-12345"},
    )
    assert r.status_code in (200, 201)
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "correct-horse-12345"},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def test_request_id_cannot_substitute_for_token() -> None:
    """Passing a request ID in place of a token must not authenticate."""
    token = _register_and_token()
    # Get a request ID from a real request.
    r = client.get(
        "/api/v1/health/live",
        headers={"X-Request-ID": "some-rid"},
    )
    rid = r.headers.get("X-Request-ID")
    assert rid

    # Now use that rid as a bearer token.
    r = client.get(
        "/api/v1/reports",
        headers={"Authorization": f"Bearer {rid}"},
    )
    assert r.status_code == 401

    # Sanity: real token works.
    r = client.get(
        "/api/v1/reports",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
