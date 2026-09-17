"""Report CRUD tests.

Each test creates its own user(s) with unique emails and cleans up
afterward. No dependency on local data.

The soft-delete tests assert on the raw ``reports`` row via
``SessionLocal`` to prove the row is preserved.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.models.report import Report
from app.db.models.user import User
from app.db.session import SessionLocal
from app.main import app
from app.services.rate_limit import set_login_rate_limiter

client = TestClient(app)


# ===========================================================================
# Fixtures
# ===========================================================================
@pytest.fixture(autouse=True)
def fresh_rate_limiter() -> Iterator[None]:
    set_login_rate_limiter(None)
    yield
    set_login_rate_limiter(None)


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    """Track user IDs created in a test; remove them (and their reports)
    on teardown. ``reports.user_id`` is ON DELETE RESTRICT, so reports
    are physically deleted first — this is test cleanup, not the API
    delete path."""
    user_ids: list[uuid.UUID] = []
    yield user_ids
    if not user_ids:
        return
    with SessionLocal() as db:
        db.execute(delete(Report).where(Report.user_id.in_(user_ids)))
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


def _unique_email(prefix: str = "reports") -> str:
    return f"{prefix}-{uuid.uuid4().hex}@example.com"


def _register_and_login(
    cleanup_users: list[uuid.UUID],
) -> tuple[uuid.UUID, str]:
    email = _unique_email()
    password = "Correct Horse Battery Staple!"

    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert r.status_code == 201, r.text
    user_id = uuid.UUID(r.json()["id"])
    cleanup_users.append(user_id)

    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return user_id, r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_report(token: str, topic: str = "Test topic") -> dict:
    r = client.post(
        "/api/v1/reports",
        headers=_auth(token),
        json={"topic": topic, "output_language": "en"},
    )
    assert r.status_code == 201, r.text
    return r.json()


# ===========================================================================
# Authentication required
# ===========================================================================
def test_create_requires_auth() -> None:
    r = client.post(
        "/api/v1/reports",
        json={"topic": "x", "output_language": "en"},
    )
    assert r.status_code == 401


def test_list_requires_auth() -> None:
    assert client.get("/api/v1/reports").status_code == 401


def test_get_requires_auth() -> None:
    assert client.get(f"/api/v1/reports/{uuid.uuid4()}").status_code == 401


def test_patch_requires_auth() -> None:
    assert (
        client.patch(f"/api/v1/reports/{uuid.uuid4()}", json={}).status_code
        == 401
    )


def test_delete_requires_auth() -> None:
    assert client.delete(f"/api/v1/reports/{uuid.uuid4()}").status_code == 401


# ===========================================================================
# Create
# ===========================================================================
def test_create_returns_201(cleanup_users: list[uuid.UUID]) -> None:
    _, token = _register_and_login(cleanup_users)
    body = _create_report(token, topic="My first report")
    assert body["topic"] == "My first report"
    assert body["output_language"] == "en"
    assert body["status"] == "draft"
    assert "id" in body
    assert "user_id" not in body
    assert "deleted_at" not in body
    assert "failed_at_phase" not in body


def test_create_persists_owner(cleanup_users: list[uuid.UUID]) -> None:
    user_id, token = _register_and_login(cleanup_users)
    body = _create_report(token, topic="Owned")
    report_id = uuid.UUID(body["id"])

    with SessionLocal() as db:
        row = db.get(Report, report_id)
        assert row is not None
        assert row.user_id == user_id
        assert row.deleted_at is None
        assert row.status == "draft"


def test_create_ignores_client_owner_and_status(
    cleanup_users: list[uuid.UUID],
) -> None:
    """Extra fields like ``user_id`` or ``status`` in the body must not
    change server-controlled state."""
    user_id, token = _register_and_login(cleanup_users)
    other_user_id = uuid.uuid4()
    r = client.post(
        "/api/v1/reports",
        headers=_auth(token),
        json={
            "topic": "t",
            "output_language": "en",
            "user_id": str(other_user_id),
            "status": "completed",
            "deleted_at": "2024-01-01T00:00:00Z",
        },
    )
    assert r.status_code == 201
    report_id = uuid.UUID(r.json()["id"])
    with SessionLocal() as db:
        row = db.get(Report, report_id)
        assert row is not None
        assert row.user_id == user_id  # NOT other_user_id
        assert row.status == "draft"   # NOT "completed"
        assert row.deleted_at is None


def test_create_rejects_empty_topic(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    r = client.post(
        "/api/v1/reports",
        headers=_auth(token),
        json={"topic": "", "output_language": "en"},
    )
    assert r.status_code == 422


def test_create_requires_language(cleanup_users: list[uuid.UUID]) -> None:
    _, token = _register_and_login(cleanup_users)
    r = client.post(
        "/api/v1/reports",
        headers=_auth(token),
        json={"topic": "t"},
    )
    assert r.status_code == 422


# ===========================================================================
# List
# ===========================================================================
def test_list_empty(cleanup_users: list[uuid.UUID]) -> None:
    _, token = _register_and_login(cleanup_users)
    r = client.get("/api/v1/reports", headers=_auth(token))
    assert r.status_code == 200
    assert r.json() == []


def test_list_only_own_reports(cleanup_users: list[uuid.UUID]) -> None:
    _, token_a = _register_and_login(cleanup_users)
    _, token_b = _register_and_login(cleanup_users)

    _create_report(token_a, "A1")
    _create_report(token_a, "A2")
    _create_report(token_b, "B1")

    a_topics = {
        r["topic"]
        for r in client.get("/api/v1/reports", headers=_auth(token_a)).json()
    }
    b_topics = {
        r["topic"]
        for r in client.get("/api/v1/reports", headers=_auth(token_b)).json()
    }
    assert a_topics == {"A1", "A2"}
    assert b_topics == {"B1"}


def test_list_deterministic_ordering(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    _create_report(token, "first")
    _create_report(token, "second")
    r1 = client.get("/api/v1/reports", headers=_auth(token)).json()
    r2 = client.get("/api/v1/reports", headers=_auth(token)).json()
    assert [r["id"] for r in r1] == [r["id"] for r in r2]


def test_list_excludes_deleted(cleanup_users: list[uuid.UUID]) -> None:
    _, token = _register_and_login(cleanup_users)
    kept = _create_report(token, "kept")
    dropped = _create_report(token, "dropped")
    client.delete(f"/api/v1/reports/{dropped['id']}", headers=_auth(token))

    items = client.get("/api/v1/reports", headers=_auth(token)).json()
    ids = {it["id"] for it in items}
    assert kept["id"] in ids
    assert dropped["id"] not in ids


# ===========================================================================
# Get
# ===========================================================================
def test_get_own_report(cleanup_users: list[uuid.UUID]) -> None:
    _, token = _register_and_login(cleanup_users)
    created = _create_report(token, "lookup")
    r = client.get(
        f"/api/v1/reports/{created['id']}",
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_get_missing_returns_404(cleanup_users: list[uuid.UUID]) -> None:
    _, token = _register_and_login(cleanup_users)
    r = client.get(
        f"/api/v1/reports/{uuid.uuid4()}",
        headers=_auth(token),
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "REPORT_NOT_FOUND"


def test_get_foreign_returns_404(cleanup_users: list[uuid.UUID]) -> None:
    _, token_a = _register_and_login(cleanup_users)
    _, token_b = _register_and_login(cleanup_users)
    a_report = _create_report(token_a, "A secret")

    r = client.get(
        f"/api/v1/reports/{a_report['id']}",
        headers=_auth(token_b),
    )
    assert r.status_code == 404
    assert "A secret" not in r.text


def test_get_deleted_returns_404(cleanup_users: list[uuid.UUID]) -> None:
    _, token = _register_and_login(cleanup_users)
    created = _create_report(token, "will-be-deleted")
    client.delete(f"/api/v1/reports/{created['id']}", headers=_auth(token))

    r = client.get(
        f"/api/v1/reports/{created['id']}",
        headers=_auth(token),
    )
    assert r.status_code == 404


# ===========================================================================
# Update
# ===========================================================================
def test_patch_own_report(cleanup_users: list[uuid.UUID]) -> None:
    _, token = _register_and_login(cleanup_users)
    created = _create_report(token, "old topic")
    r = client.patch(
        f"/api/v1/reports/{created['id']}",
        headers=_auth(token),
        json={"topic": "new topic"},
    )
    assert r.status_code == 200
    assert r.json()["topic"] == "new topic"


def test_patch_preserves_untouched_fields(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    r = client.post(
        "/api/v1/reports",
        headers=_auth(token),
        json={
            "topic": "t",
            "output_language": "fa",
            "domain": "biology",
            "tone": "formal",
        },
    )
    assert r.status_code == 201
    created = r.json()

    r = client.patch(
        f"/api/v1/reports/{created['id']}",
        headers=_auth(token),
        json={"tone": "casual"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tone"] == "casual"
    assert body["domain"] == "biology"      # preserved
    assert body["output_language"] == "fa"  # preserved
    assert body["topic"] == "t"             # preserved


def test_patch_can_clear_nullable_field(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    r = client.post(
        "/api/v1/reports",
        headers=_auth(token),
        json={"topic": "t", "output_language": "en", "tone": "formal"},
    )
    created = r.json()
    r = client.patch(
        f"/api/v1/reports/{created['id']}",
        headers=_auth(token),
        json={"tone": None},
    )
    assert r.status_code == 200
    assert r.json()["tone"] is None


def test_patch_rejects_null_topic(cleanup_users: list[uuid.UUID]) -> None:
    _, token = _register_and_login(cleanup_users)
    created = _create_report(token)
    r = client.patch(
        f"/api/v1/reports/{created['id']}",
        headers=_auth(token),
        json={"topic": None},
    )
    assert r.status_code == 422


def test_patch_rejects_null_output_language(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    created = _create_report(token)
    r = client.patch(
        f"/api/v1/reports/{created['id']}",
        headers=_auth(token),
        json={"output_language": None},
    )
    assert r.status_code == 422


def test_patch_foreign_returns_404(cleanup_users: list[uuid.UUID]) -> None:
    _, token_a = _register_and_login(cleanup_users)
    _, token_b = _register_and_login(cleanup_users)
    a_report = _create_report(token_a, "A")

    r = client.patch(
        f"/api/v1/reports/{a_report['id']}",
        headers=_auth(token_b),
        json={"topic": "hijacked"},
    )
    assert r.status_code == 404

    # Owner's view is unchanged.
    r = client.get(
        f"/api/v1/reports/{a_report['id']}",
        headers=_auth(token_a),
    )
    assert r.json()["topic"] == "A"


def test_patch_deleted_returns_404(cleanup_users: list[uuid.UUID]) -> None:
    _, token = _register_and_login(cleanup_users)
    created = _create_report(token)
    client.delete(f"/api/v1/reports/{created['id']}", headers=_auth(token))

    r = client.patch(
        f"/api/v1/reports/{created['id']}",
        headers=_auth(token),
        json={"topic": "revived"},
    )
    assert r.status_code == 404


# ===========================================================================
# Delete (soft)
# ===========================================================================
def test_delete_returns_204(cleanup_users: list[uuid.UUID]) -> None:
    _, token = _register_and_login(cleanup_users)
    created = _create_report(token)
    r = client.delete(
        f"/api/v1/reports/{created['id']}", headers=_auth(token)
    )
    assert r.status_code == 204
    assert r.content == b""


def test_delete_keeps_row_in_db(cleanup_users: list[uuid.UUID]) -> None:
    _, token = _register_and_login(cleanup_users)
    created = _create_report(token, "keepme")
    report_id = uuid.UUID(created["id"])
    client.delete(f"/api/v1/reports/{report_id}", headers=_auth(token))

    with SessionLocal() as db:
        row = db.get(Report, report_id)
        assert row is not None
        assert row.deleted_at is not None
        # Status is unchanged by soft delete.
        assert row.status == "draft"


def test_delete_removes_from_list(cleanup_users: list[uuid.UUID]) -> None:
    _, token = _register_and_login(cleanup_users)
    c1 = _create_report(token, "keep")
    c2 = _create_report(token, "drop")
    client.delete(f"/api/v1/reports/{c2['id']}", headers=_auth(token))

    items = client.get("/api/v1/reports", headers=_auth(token)).json()
    ids = {it["id"] for it in items}
    assert c1["id"] in ids
    assert c2["id"] not in ids


def test_delete_is_not_repeatable(cleanup_users: list[uuid.UUID]) -> None:
    _, token = _register_and_login(cleanup_users)
    created = _create_report(token)
    first = client.delete(
        f"/api/v1/reports/{created['id']}", headers=_auth(token)
    )
    assert first.status_code == 204
    second = client.delete(
        f"/api/v1/reports/{created['id']}", headers=_auth(token)
    )
    assert second.status_code == 404
    assert second.json()["error"]["code"] == "REPORT_NOT_FOUND"


def test_delete_foreign_returns_404(cleanup_users: list[uuid.UUID]) -> None:
    _, token_a = _register_and_login(cleanup_users)
    _, token_b = _register_and_login(cleanup_users)
    a_report = _create_report(token_a)

    r = client.delete(
        f"/api/v1/reports/{a_report['id']}",
        headers=_auth(token_b),
    )
    assert r.status_code == 404

    # Owner still sees the report.
    r = client.get(
        f"/api/v1/reports/{a_report['id']}",
        headers=_auth(token_a),
    )
    assert r.status_code == 200


# ===========================================================================
# IDOR regression
# ===========================================================================
def test_idor_no_cross_user_access(cleanup_users: list[uuid.UUID]) -> None:
    _, token_a = _register_and_login(cleanup_users)
    _, token_b = _register_and_login(cleanup_users)
    a_report = _create_report(token_a, "A only")

    assert client.get(
        f"/api/v1/reports/{a_report['id']}", headers=_auth(token_b)
    ).status_code == 404

    assert client.patch(
        f"/api/v1/reports/{a_report['id']}",
        headers=_auth(token_b),
        json={"topic": "hijacked"},
    ).status_code == 404

    assert client.delete(
        f"/api/v1/reports/{a_report['id']}", headers=_auth(token_b)
    ).status_code == 404

    b_list = client.get("/api/v1/reports", headers=_auth(token_b)).json()
    assert a_report["id"] not in {x["id"] for x in b_list}
