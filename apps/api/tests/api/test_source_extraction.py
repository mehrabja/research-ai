"""Source extraction API tests.

The fetcher is monkeypatched so no live HTTP calls are made. The
extractor pipeline is real (domain canonicalization + chunking).
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from app.db.models.report import Report, ReportEvent
from app.db.models.source import Chunk, Source
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.main import app
from app.services import extraction as extraction_service
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
    """Track users and cascade-clean everything they own."""
    user_ids: list[uuid.UUID] = []
    yield user_ids
    if not user_ids:
        return

    with SessionLocal() as db:
        report_ids_subq = select(Report.id).where(
            Report.user_id.in_(user_ids)
        )
        source_ids_subq = select(Source.id).where(
            Source.report_id.in_(report_ids_subq)
        )
        db.execute(
            delete(Chunk).where(Chunk.source_id.in_(source_ids_subq))
        )
        db.execute(
            delete(ReportEvent).where(
                ReportEvent.report_id.in_(report_ids_subq)
            )
        )
        db.execute(
            delete(Source).where(Source.report_id.in_(report_ids_subq))
        )
        db.execute(delete(Report).where(Report.user_id.in_(user_ids)))
        # M37: purge owned workspaces before deleting user
        db.execute(
            delete(Workspace).where(
                Workspace.owner_user_id.in_(user_ids)
            )
        )
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


def _unique_email() -> str:
    return f"extr-{uuid.uuid4().hex}@example.com"


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


def _add_source_direct(
    *, report_id: uuid.UUID, url: str | None
) -> uuid.UUID:
    """Insert a source row directly, bypassing any source API."""
    with SessionLocal() as db:
        sid = db.execute(
            text(
                "INSERT INTO sources "
                "(report_id, title, url, status) "
                "VALUES (:r, 'T', :u, 'metadata_only') RETURNING id"
            ),
            {"r": report_id, "u": url},
        ).scalar()
        db.commit()
    return sid


class _FakeFetched:
    def __init__(
        self,
        *,
        content: bytes,
        content_type: str,
        content_length: int | None = None,
    ) -> None:
        self.url = "https://example.org/x"
        self.final_url = self.url
        self.content_type = content_type
        self.content = content
        self.content_length = (
            content_length if content_length is not None else len(content)
        )


def _mock_fetch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    body: bytes,
    content_type: str,
) -> None:
    def _fake(
        url: str,
        *,
        max_bytes: int,
        timeout_seconds: float,
        max_redirects: int,
    ) -> _FakeFetched:
        return _FakeFetched(content=body, content_type=content_type)

    monkeypatch.setattr(extraction_service, "fetch_document", _fake)


# ===========================================================================
# Auth
# ===========================================================================
def test_extract_requires_auth() -> None:
    r = client.post(
        f"/api/v1/reports/{uuid.uuid4()}"
        f"/sources/{uuid.uuid4()}/extract"
    )
    assert r.status_code == 401


# ===========================================================================
# Ownership
# ===========================================================================
def test_extract_foreign_report_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token_a = _register_and_login(cleanup_users)
    _, token_b = _register_and_login(cleanup_users)
    report_b = _create_report(token_b)
    sid = _add_source_direct(
        report_id=uuid.UUID(report_b["id"]), url="https://x.test/a"
    )
    r = client.post(
        f"/api/v1/reports/{report_b['id']}/sources/{sid}/extract",
        headers=_auth(token_a),
    )
    assert r.status_code == 404


def test_extract_foreign_source_under_own_report_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token_a = _register_and_login(cleanup_users)
    _, token_b = _register_and_login(cleanup_users)
    report_a = _create_report(token_a)
    report_b = _create_report(token_b)
    sid_b = _add_source_direct(
        report_id=uuid.UUID(report_b["id"]), url="https://x.test/b"
    )
    r = client.post(
        f"/api/v1/reports/{report_a['id']}/sources/{sid_b}/extract",
        headers=_auth(token_a),
    )
    assert r.status_code == 404


def test_extract_deleted_report_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    sid = _add_source_direct(
        report_id=uuid.UUID(report["id"]), url="https://x.test/c"
    )
    client.delete(
        f"/api/v1/reports/{report['id']}", headers=_auth(token)
    )
    r = client.post(
        f"/api/v1/reports/{report['id']}/sources/{sid}/extract",
        headers=_auth(token),
    )
    assert r.status_code == 404


# ===========================================================================
# Pre-persistence failure: no URL
# ===========================================================================
def test_extract_without_url_records_failure(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    sid = _add_source_direct(
        report_id=uuid.UUID(report["id"]), url=None
    )
    r = client.post(
        f"/api/v1/reports/{report['id']}/sources/{sid}/extract",
        headers=_auth(token),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "SOURCE_DOCUMENT_URL_MISSING"
    with SessionLocal() as db:
        row = db.execute(
            text(
                "SELECT extraction_error, status FROM sources "
                "WHERE id = :s"
            ),
            {"s": sid},
        ).one()
    assert row.extraction_error == "no_url"
    assert row.status == "extraction_failed"


# ===========================================================================
# Happy path
# ===========================================================================
def test_extract_plain_text_success(
    cleanup_users: list[uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    sid = _add_source_direct(
        report_id=uuid.UUID(report["id"]), url="https://x.test/ok"
    )
    _mock_fetch(
        monkeypatch,
        body=b"Alpha beta gamma delta epsilon zeta eta theta iota",
        content_type="text/plain",
    )

    r = client.post(
        f"/api/v1/reports/{report['id']}/sources/{sid}/extract",
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "full_text"
    assert body["chunk_count"] >= 1
    assert body["content_hash"] is not None
    assert len(body["content_hash"]) == 64
    assert body["pipeline_version"] == "m8.1"
    assert body["content_type"] == "text/plain"

    # No content leak in response.
    assert "Alpha" not in r.text
    assert "beta" not in r.text


def test_extract_creates_source_extracted_event(
    cleanup_users: list[uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    sid = _add_source_direct(
        report_id=uuid.UUID(report["id"]), url="https://x.test/ev"
    )
    _mock_fetch(
        monkeypatch, body=b"some text", content_type="text/plain"
    )
    client.post(
        f"/api/v1/reports/{report['id']}/sources/{sid}/extract",
        headers=_auth(token),
    )
    r = client.get(
        f"/api/v1/reports/{report['id']}/events",
        headers=_auth(token),
    )
    events = r.json()
    assert len(events) == 1
    assert events[0]["event_type"] == "source_extracted"
    meta = events[0]["metadata"]
    assert meta["chunk_count"] >= 1
    assert meta["pipeline_version"] == "m8.1"
    assert meta["source_id"] == str(sid)


# ===========================================================================
# Idempotency
# ===========================================================================
def test_repeat_extract_same_content_is_idempotent(
    cleanup_users: list[uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    sid = _add_source_direct(
        report_id=uuid.UUID(report["id"]), url="https://x.test/idem"
    )
    body = b"same content for idempotency test"
    _mock_fetch(monkeypatch, body=body, content_type="text/plain")

    r1 = client.post(
        f"/api/v1/reports/{report['id']}/sources/{sid}/extract",
        headers=_auth(token),
    )
    assert r1.status_code == 200
    with SessionLocal() as db:
        first_extracted_at = db.execute(
            text("SELECT extracted_at FROM sources WHERE id = :s"),
            {"s": sid},
        ).scalar()
        first_chunk_ids = {
            row[0]
            for row in db.execute(
                text("SELECT id FROM chunks WHERE source_id = :s"),
                {"s": sid},
            ).all()
        }

    r2 = client.post(
        f"/api/v1/reports/{report['id']}/sources/{sid}/extract",
        headers=_auth(token),
    )
    assert r2.status_code == 200
    with SessionLocal() as db:
        second_extracted_at = db.execute(
            text("SELECT extracted_at FROM sources WHERE id = :s"),
            {"s": sid},
        ).scalar()
        second_chunk_ids = {
            row[0]
            for row in db.execute(
                text("SELECT id FROM chunks WHERE source_id = :s"),
                {"s": sid},
            ).all()
        }
        event_count = db.execute(
            text(
                "SELECT count(*) FROM report_events "
                "WHERE report_id = :r AND event_type = 'source_extracted'"
            ),
            {"r": report["id"]},
        ).scalar()

    assert first_extracted_at == second_extracted_at
    assert first_chunk_ids == second_chunk_ids
    assert event_count == 1


# ===========================================================================
# Failure boundaries
# ===========================================================================
def test_unsupported_content_type_records_failure(
    cleanup_users: list[uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    sid = _add_source_direct(
        report_id=uuid.UUID(report["id"]), url="https://x.test/bin"
    )
    _mock_fetch(
        monkeypatch,
        body=b"\x00\x01\x02",
        content_type="application/octet-stream",
    )
    r = client.post(
        f"/api/v1/reports/{report['id']}/sources/{sid}/extract",
        headers=_auth(token),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "UNSUPPORTED_CONTENT_TYPE"
    with SessionLocal() as db:
        row = db.execute(
            text(
                "SELECT extraction_error, status FROM sources "
                "WHERE id = :s"
            ),
            {"s": sid},
        ).one()
    assert row.extraction_error == "unsupported_content_type"
    assert row.status == "extraction_failed"


def test_persistence_failure_does_not_corrupt_previous_success(
    cleanup_users: list[uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, token = _register_and_login(cleanup_users)
    report = _create_report(token)
    sid = _add_source_direct(
        report_id=uuid.UUID(report["id"]), url="https://x.test/v2"
    )
    _mock_fetch(
        monkeypatch, body=b"v1 content", content_type="text/plain"
    )
    client.post(
        f"/api/v1/reports/{report['id']}/sources/{sid}/extract",
        headers=_auth(token),
    )
    with SessionLocal() as db:
        v1 = db.execute(
            text(
                "SELECT full_text, content_hash, extracted_at, status, "
                "extraction_error, extraction_pipeline_version "
                "FROM sources WHERE id = :s"
            ),
            {"s": sid},
        ).one()

    def _fail(*_args, **_kwargs):
        raise RuntimeError("simulated event insert failure")

    _mock_fetch(
        monkeypatch, body=b"v2 different", content_type="text/plain"
    )
    monkeypatch.setattr(
        extraction_service, "create_source_extracted_event", _fail
    )

    # TestClient re-raises unhandled server-side exceptions by default.
    # We assert the simulated failure bubbles up, then verify the DB
    # state was rolled back to the previous successful extraction.
    with pytest.raises(RuntimeError):
        client.post(
            f"/api/v1/reports/{report['id']}/sources/{sid}/extract",
            headers=_auth(token),
        )

    with SessionLocal() as db:
        v2 = db.execute(
            text(
                "SELECT full_text, content_hash, extracted_at, status, "
                "extraction_error, extraction_pipeline_version "
                "FROM sources WHERE id = :s"
            ),
            {"s": sid},
        ).one()
    assert v1 == v2
