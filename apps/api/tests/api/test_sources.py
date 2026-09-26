"""Source API tests: search / create / list / get + ownership."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.api.routes.sources import _default_provider
from app.db.models.report import Report, ReportEvent
from app.db.models.source import Chunk, Source
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.domain.source import SourceCandidate
from app.main import app
from app.services.rate_limit import set_login_rate_limiter

client = TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_limiter() -> Iterator[None]:
    set_login_rate_limiter(None)
    yield
    set_login_rate_limiter(None)


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    ids: list[uuid.UUID] = []
    yield ids
    if not ids:
        return
    with SessionLocal() as db:
        report_ids_subq = select(Report.id).where(
            Report.user_id.in_(ids)
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
        db.execute(delete(Report).where(Report.user_id.in_(ids)))
        # M37: purge owned workspaces before deleting user
        db.execute(
            delete(Workspace).where(
                Workspace.owner_user_id.in_(ids)
            )
        )
        db.execute(delete(User).where(User.id.in_(ids)))
        db.commit()


class _FakeProvider:
    provider_name = "fake"

    def __init__(
        self,
        *,
        candidates: list[SourceCandidate] | None = None,
        error: BaseException | None = None,
    ) -> None:
        self._candidates = candidates or []
        self._error = error

    def search(
        self,
        *,
        query: str,
        limit: int,
        year: int | None = None,
        open_access_only: bool = False,
    ) -> list[SourceCandidate]:
        if self._error is not None:
            raise self._error
        return list(self._candidates)


@pytest.fixture()
def override_provider() -> Iterator[dict]:
    holder: dict = {"provider": _FakeProvider()}
    app.dependency_overrides[_default_provider] = lambda: holder["provider"]
    try:
        yield holder
    finally:
        app.dependency_overrides.pop(_default_provider, None)


def _auth(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


def _register(ids: list[uuid.UUID]) -> tuple[uuid.UUID, str]:
    email = f"srca-{uuid.uuid4().hex}@example.com"
    pw = "Correct Horse Battery Staple!"
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": pw},
    )
    assert r.status_code == 201, r.text
    uid = uuid.UUID(r.json()["id"])
    ids.append(uid)
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": pw},
    )
    assert r.status_code == 200, r.text
    return uid, r.json()["access_token"]


def _create_report(token: str, topic: str = "T") -> dict:
    r = client.post(
        "/api/v1/reports",
        headers=_auth(token),
        json={"topic": topic, "output_language": "en"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _payload(ext: str = "P1") -> dict:
    return {
        "source_api": "semantic_scholar",
        "external_source_id": ext,
        "title": "T",
        "authors": ["A"],
        "year": 2020,
        "doi": "10.1/x",
        "url": "https://example.org/p",
        "abstract": "abs",
        "citation_count": 5,
    }


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def test_search_requires_auth() -> None:
    r = client.get(
        f"/api/v1/reports/{uuid.uuid4()}/sources/search?q=x"
    )
    assert r.status_code == 401


def test_create_requires_auth() -> None:
    r = client.post(
        f"/api/v1/reports/{uuid.uuid4()}/sources", json=_payload()
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
def test_search_returns_candidates(
    cleanup_users: list[uuid.UUID],
    override_provider: dict,
) -> None:
    _, token = _register(cleanup_users)
    rep = _create_report(token)
    override_provider["provider"] = _FakeProvider(
        candidates=[
            SourceCandidate(
                source_api="semantic_scholar",
                external_source_id="P1",
                title="T1",
            )
        ]
    )
    r = client.get(
        f"/api/v1/reports/{rep['id']}/sources/search?q=hello",
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["query"] == "hello"
    assert len(body["candidates"]) == 1
    assert body["candidates"][0]["external_source_id"] == "P1"


def test_search_foreign_report_404(
    cleanup_users: list[uuid.UUID],
    override_provider: dict,
) -> None:
    _, token_a = _register(cleanup_users)
    _, token_b = _register(cleanup_users)
    rep_b = _create_report(token_b)
    r = client.get(
        f"/api/v1/reports/{rep_b['id']}/sources/search?q=x",
        headers=_auth(token_a),
    )
    assert r.status_code == 404


def test_search_empty_query_422(
    cleanup_users: list[uuid.UUID],
    override_provider: dict,
) -> None:
    _, token = _register(cleanup_users)
    rep = _create_report(token)
    r = client.get(
        f"/api/v1/reports/{rep['id']}/sources/search?q=",
        headers=_auth(token),
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Create / List / Get
# ---------------------------------------------------------------------------
def test_create_source_201(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register(cleanup_users)
    rep = _create_report(token)
    r = client.post(
        f"/api/v1/reports/{rep['id']}/sources",
        headers=_auth(token),
        json=_payload(),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "metadata_only"
    assert body["external_source_id"] == "P1"
    assert "full_text" not in body
    assert "source_meta" not in body


def test_create_duplicate_is_idempotent(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register(cleanup_users)
    rep = _create_report(token)
    r1 = client.post(
        f"/api/v1/reports/{rep['id']}/sources",
        headers=_auth(token),
        json=_payload(),
    )
    r2 = client.post(
        f"/api/v1/reports/{rep['id']}/sources",
        headers=_auth(token),
        json=_payload(),
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


def test_list_sources(cleanup_users: list[uuid.UUID]) -> None:
    _, token = _register(cleanup_users)
    rep = _create_report(token)
    client.post(
        f"/api/v1/reports/{rep['id']}/sources",
        headers=_auth(token),
        json=_payload("P1"),
    )
    client.post(
        f"/api/v1/reports/{rep['id']}/sources",
        headers=_auth(token),
        json=_payload("P2"),
    )
    r = client.get(
        f"/api/v1/reports/{rep['id']}/sources",
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert len(r.json()["items"]) == 2


def test_get_source(cleanup_users: list[uuid.UUID]) -> None:
    _, token = _register(cleanup_users)
    rep = _create_report(token)
    r = client.post(
        f"/api/v1/reports/{rep['id']}/sources",
        headers=_auth(token),
        json=_payload(),
    )
    sid = r.json()["id"]
    r2 = client.get(
        f"/api/v1/reports/{rep['id']}/sources/{sid}",
        headers=_auth(token),
    )
    assert r2.status_code == 200
    assert r2.json()["id"] == sid


def test_get_source_foreign_user_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token_a = _register(cleanup_users)
    _, token_b = _register(cleanup_users)
    rep_a = _create_report(token_a)
    r = client.post(
        f"/api/v1/reports/{rep_a['id']}/sources",
        headers=_auth(token_a),
        json=_payload(),
    )
    sid = r.json()["id"]
    r2 = client.get(
        f"/api/v1/reports/{rep_a['id']}/sources/{sid}",
        headers=_auth(token_b),
    )
    assert r2.status_code == 404


def test_deleted_report_404(
    cleanup_users: list[uuid.UUID],
) -> None:
    _, token = _register(cleanup_users)
    rep = _create_report(token)
    client.delete(
        f"/api/v1/reports/{rep['id']}", headers=_auth(token)
    )
    r = client.get(
        f"/api/v1/reports/{rep['id']}/sources",
        headers=_auth(token),
    )
    assert r.status_code == 404


def test_search_provider_error_maps_502(
    cleanup_users: list[uuid.UUID],
    override_provider: dict,
) -> None:
    from app.integrations.sources.base import (
        SourceProviderUnavailableError,
    )

    _, token = _register(cleanup_users)
    rep = _create_report(token)
    override_provider["provider"] = _FakeProvider(
        error=SourceProviderUnavailableError()
    )
    r = client.get(
        f"/api/v1/reports/{rep['id']}/sources/search?q=x",
        headers=_auth(token),
    )
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "SOURCE_PROVIDER_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Extraction regression — M8 endpoint still works
# ---------------------------------------------------------------------------
def test_extraction_endpoint_still_registered() -> None:
    schema = app.openapi()
    paths = schema.get("paths", {})
    assert any(
        p.endswith("/sources/{source_id}/extract") for p in paths
    )
