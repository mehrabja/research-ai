"""Report events API tests.

Covers: ownership isolation, event shapes, atomicity between the
mutation and its audit event, and immutability of the events surface.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from app.db.models.report import Report, ReportEvent, ReportVersion
from app.db.models.user import User
from app.db.session import SessionLocal
from app.main import app
from app.services import report_status as report_status_service
from app.services import report_versions as report_versions_service
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
    """Track users created in a test and remove everything they own.

    Deletion order is FK-safe:

    1. ``report_events`` — the shape CHECK forbids nulling
       ``version_id`` on ``version_created`` events, so events must
       go before their referenced versions.
    2. ``report_versions`` — ``reports`` FK is RESTRICT.
    3. ``reports``
    4. ``users``
    """
    user_ids: list[uuid.UUID] = []
    yield user_ids
    if not user_ids:
        return

    with SessionLocal() as db:
        report_ids_subq = select(Report.id).where(
            Report.user_id.in_(user_ids)
        )
        db.execute(
            delete(ReportEvent).where(
                ReportEvent.report_id.in_(report_ids_subq)
            )
        )
        db.execute(
            delete(ReportVersion).where(
                ReportVersion.report_id.in_(report_ids_subq)
            )
        )
        db.execute(delete(Report).where(Report.user_id.in_(user_ids)))
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


def _unique_email() -> str:
    return f"events-{uuid.uuid4().hex}@example.com"


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


def _create_report(token: str, topic: str = "T") -> dict:
    r = client.post(
        "/api/v1/reports",
        headers=_auth(token),
        json={"topic": topic, "output_language": "en"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _transition(token: str, report_id: str, status: str):
    return client.patch(
        f"/api/v1/reports/{report_id}/status",
        headers=_auth(token),
        json={"status": status},
    )


def _create_version(token: str, report_id: str, language: str = "en"):
    return client.post(
        f"/api/v1/reports/{report_id}/versions",
        headers=_auth(token),
        json={"language": language, "content": "hello"},
    )


def _list_events(token: str, report_id: str):
    return client.get(
        f"/api/v1/reports/{report_id}/events",
        headers=_auth(token),
    )


# ===========================================================================
# Auth + isolation
# ===========================================================================
def test_events_requires_auth() -> None:
    r = client.get(f"/api/v1/reports/{uuid.uuid4()}/events")
    assert r.status_code == 401


def test_empty_events(cleanup_users: list[uuid.UUID]) -> None:
    _, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    r = _list_events(token, report["id"])
    assert r.status_code == 200
    assert r.json() == []


def test_events_foreign_report_returns_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token_a = _register_and_login(cleanup_users)
    _, token_b = _register_and_login(cleanup_users)
    a_report = _create_report(token_a, "A secret")
    r = _list_events(token_b, a_report["id"])
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "REPORT_NOT_FOUND"


def test_events_deleted_report_returns_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    client.delete(
        f"/api/v1/reports/{report['id']}",
        headers=_auth(token),
    )
    r = _list_events(token, report["id"])
    assert r.status_code == 404


# ===========================================================================
# Shape of events
# ===========================================================================
def test_status_transition_creates_one_event(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    r = _transition(token, report["id"], "searching")
    assert r.status_code == 200

    events = _list_events(token, report["id"]).json()
    assert len(events) == 1
    ev = events[0]
    assert ev["event_type"] == "status_transition"
    assert ev["from_status"] == "draft"
    assert ev["to_status"] == "searching"
    assert ev["version_id"] is None
    assert ev["user_id"] is not None
    assert ev["report_id"] == report["id"]
    assert ev["metadata"] is None


def test_same_status_creates_no_event(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    _transition(token, report["id"], "searching")
    r = _transition(token, report["id"], "searching")
    assert r.status_code == 200

    events = _list_events(token, report["id"]).json()
    assert len(events) == 1


def test_version_creation_creates_event(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    r = _create_version(token, report["id"])
    assert r.status_code == 201, r.text
    version_id = r.json()["id"]

    events = _list_events(token, report["id"]).json()
    assert len(events) == 1
    ev = events[0]
    assert ev["event_type"] == "version_created"
    assert ev["version_id"] == version_id
    assert ev["from_status"] is None
    assert ev["to_status"] is None


def test_events_contain_both_types(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    _transition(token, report["id"], "searching")
    _create_version(token, report["id"])
    _transition(token, report["id"], "extracting")

    events = _list_events(token, report["id"]).json()
    types = sorted(e["event_type"] for e in events)
    assert types == [
        "status_transition",
        "status_transition",
        "version_created",
    ]


def test_invalid_transition_creates_no_event(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    # draft -> completed is not a legal transition.
    r = _transition(token, report["id"], "completed")
    assert r.status_code == 409
    events = _list_events(token, report["id"]).json()
    assert events == []


# ===========================================================================
# Security
# ===========================================================================
def test_event_response_has_no_secrets(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    _transition(token, report["id"], "searching")

    body = _list_events(token, report["id"]).text.lower()
    assert "password" not in body
    assert "hash" not in body
    assert "secret" not in body


def test_events_have_no_mutation_endpoints(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    _transition(token, report["id"], "searching")
    path = f"/api/v1/reports/{report['id']}/events"

    for method in ("post", "put", "patch", "delete"):
        r = getattr(client, method)(path, headers=_auth(token))
        assert r.status_code in (404, 405), (
            f"{method.upper()} {path}: {r.status_code}"
        )


# ===========================================================================
# Application-level validation
# ===========================================================================
def test_unknown_status_value_rejected_by_service(
    cleanup_users: list[uuid.UUID],
) -> None:
    from app.core.exceptions import ReportEventValidationError
    from app.services import report_events as report_events_service

    _, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    report_id = uuid.UUID(report["id"])

    with SessionLocal() as db, pytest.raises(ReportEventValidationError):
        report_events_service.create_status_transition_event(
            db,
            report_id=report_id,
            user_id=None,
            from_status="banana_status",
            to_status="searching",
        )


# ===========================================================================
# Atomicity: mutation + audit event
# ===========================================================================
def test_status_update_rolls_back_on_event_failure(
    cleanup_users: list[uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the event insert raises after the UPDATE but before COMMIT,
    the status mutation must roll back.
    """

    def _fail(*_args, **_kwargs):
        raise RuntimeError("simulated event insert failure")

    monkeypatch.setattr(
        report_status_service,
        "create_status_transition_event",
        _fail,
    )

    user_id, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    report_id = uuid.UUID(report["id"])

    with SessionLocal() as db, pytest.raises(RuntimeError):
        report_status_service.update_report_status(
            db,
            user_id=user_id,
            report_id=report_id,
            new_status="searching",
        )

    with SessionLocal() as db2:
        row = db2.get(Report, report_id)
        assert row is not None
        assert row.status == "draft"

        count = db2.execute(
            text("SELECT count(*) FROM report_events WHERE report_id = :r"),
            {"r": report_id},
        ).scalar()
        assert count == 0


def test_version_creation_rolls_back_on_event_failure(
    cleanup_users: list[uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the event insert raises after version.flush() but before
    COMMIT, both the version and its audit event must roll back.
    """

    def _fail(*_args, **_kwargs):
        raise RuntimeError("simulated event insert failure")

    monkeypatch.setattr(
        report_versions_service,
        "create_version_created_event",
        _fail,
    )

    user_id, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    report_id = uuid.UUID(report["id"])

    with SessionLocal() as db, pytest.raises(RuntimeError):
        report_versions_service.create_report_version(
            db,
            user_id=user_id,
            report_id=report_id,
            language="en",
            content="will not persist",
        )

    with SessionLocal() as db2:
        vcount = db2.execute(
            text("SELECT count(*) FROM report_versions WHERE report_id = :r"),
            {"r": report_id},
        ).scalar()
        assert vcount == 0

        ecount = db2.execute(
            text("SELECT count(*) FROM report_events WHERE report_id = :r"),
            {"r": report_id},
        ).scalar()
        assert ecount == 0
