"""M36 — storage download hardening tests.

Verifies that the file download route emits a Content-Length header
matching the recorded size.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_download_content_length_header() -> None:
    # Register + login + project + upload + download
    import uuid

    email = f"m36-{uuid.uuid4().hex[:8]}@example.com"
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
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post(
        "/api/v1/projects",
        json={"name": "m36-storage"},
        headers=headers,
    )
    assert r.status_code in (200, 201)
    pid = r.json()["id"]

    payload = b"hello world" * 10
    r = client.post(
        f"/api/v1/projects/{pid}/files",
        files={"file": ("x.txt", payload, "text/plain")},
        headers=headers,
    )
    assert r.status_code in (200, 201), r.text
    fid = r.json()["id"]

    r = client.get(f"/api/v1/files/{fid}/content", headers=headers)
    assert r.status_code == 200
    assert r.headers.get("Content-Length") == str(len(payload))
    assert r.content == payload
