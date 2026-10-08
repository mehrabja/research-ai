"""Source service tests: ownership, idempotency, event emission."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.core import exceptions as exc
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.domain.source import SourceCandidate
from app.integrations.sources.base import (
    SourceProviderRateLimitError,
    SourceProviderUnavailableError,
)
from app.services import sources as sources_service


def _seed_report(
    *, status: str = "draft", deleted: bool = False
) -> tuple[uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        uid = db.execute(
            text(
                "INSERT INTO users (email, password_hash) "
                "VALUES (:e, 'h') RETURNING id"
            ),
            {"e": f"src-{uuid.uuid4().hex}@example.com"},
        ).scalar()
        rid = db.execute(
            text(
                "INSERT INTO reports "
                "(user_id, topic, status, output_language) "
                "VALUES (:u, 'T', :s, 'en') RETURNING id"
            ),
            {"u": uid, "s": status},
        ).scalar()
        if deleted:
            db.execute(
                text(
                    "UPDATE reports SET deleted_at = now() WHERE id = :r"
                ),
                {"r": rid},
            )
        db.commit()
    return uid, rid


def _candidate(*, ext: str = "P1", title: str = "T") -> SourceCandidate:
    return SourceCandidate(
        source_api="semantic_scholar",
        external_source_id=ext,
        title=title,
        authors=("A",),
        year=2020,
        doi="10.1/x",
        url="https://example.org/p",
        abstract="abs",
        citation_count=5,
    )


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
        self.calls: list[dict] = []

    def search(
        self,
        *,
        query: str,
        limit: int,
        year: int | None = None,
        open_access_only: bool = False,
    ) -> list[SourceCandidate]:
        self.calls.append(
            {
                "query": query,
                "limit": limit,
                "year": year,
                "open_access_only": open_access_only,
            }
        )
        if self._error is not None:
            raise self._error
        return list(self._candidates)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
def test_search_returns_candidates_no_persist() -> None:
    uid, rid = _seed_report()
    prov = _FakeProvider(candidates=[_candidate()])
    with SessionLocal() as db:
        out = sources_service.search_source_candidates(
            db,
            user_id=uid,
            report_id=rid,
            query="  q  ",
            limit=5,
            provider=prov,
        )
    assert len(out) == 1
    assert prov.calls[0]["query"] == "q"
    assert prov.calls[0]["limit"] == 5
    with SessionLocal() as db:
        cnt = db.execute(
            text("SELECT count(*) FROM sources WHERE report_id = :r"),
            {"r": rid},
        ).scalar()
    assert cnt == 0


def test_search_empty_query_rejected() -> None:
    uid, rid = _seed_report()
    prov = _FakeProvider()
    with SessionLocal() as db, pytest.raises(exc.SourceQueryInvalid):
        sources_service.search_source_candidates(
            db,
            user_id=uid,
            report_id=rid,
            query="   ",
            limit=5,
            provider=prov,
        )


def test_search_limit_clamped_to_max() -> None:
    uid, rid = _seed_report()
    prov = _FakeProvider()
    with SessionLocal() as db:
        sources_service.search_source_candidates(
            db,
            user_id=uid,
            report_id=rid,
            query="q",
            limit=9999,
            provider=prov,
        )
    assert prov.calls[0]["limit"] == get_settings().source_search_limit_max


def test_search_foreign_report_raises() -> None:
    _, rid_a = _seed_report()
    uid_b, _ = _seed_report()
    prov = _FakeProvider()
    with SessionLocal() as db, pytest.raises(exc.ReportNotFound):
        sources_service.search_source_candidates(
            db,
            user_id=uid_b,
            report_id=rid_a,
            query="q",
            limit=5,
            provider=prov,
        )


def test_search_deleted_report_raises() -> None:
    uid, rid = _seed_report(deleted=True)
    prov = _FakeProvider()
    with SessionLocal() as db, pytest.raises(exc.ReportNotFound):
        sources_service.search_source_candidates(
            db,
            user_id=uid,
            report_id=rid,
            query="q",
            limit=5,
            provider=prov,
        )


def test_search_provider_unavailable_maps() -> None:
    uid, rid = _seed_report()
    prov = _FakeProvider(error=SourceProviderUnavailableError())
    with SessionLocal() as db, pytest.raises(
        exc.SourceProviderUnavailable
    ):
        sources_service.search_source_candidates(
            db,
            user_id=uid,
            report_id=rid,
            query="q",
            limit=5,
            provider=prov,
        )


def test_search_rate_limited_maps() -> None:
    uid, rid = _seed_report()
    prov = _FakeProvider(error=SourceProviderRateLimitError())
    with SessionLocal() as db, pytest.raises(
        exc.SourceProviderRateLimited
    ):
        sources_service.search_source_candidates(
            db,
            user_id=uid,
            report_id=rid,
            query="q",
            limit=5,
            provider=prov,
        )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
def test_create_source_persists() -> None:
    uid, rid = _seed_report()
    with SessionLocal() as db:
        source, created = (
            sources_service.create_source_from_candidate(
                db, user_id=uid, report_id=rid, candidate=_candidate()
            )
        )
    assert created is True
    with SessionLocal() as db:
        row = db.execute(
            text(
                "SELECT title, status, source_api, external_source_id "
                "FROM sources WHERE id = :i"
            ),
            {"i": source.id},
        ).one()
    assert row.title == "T"
    assert row.status == "metadata_only"
    assert row.source_api == "semantic_scholar"
    assert row.external_source_id == "P1"


def test_create_source_creates_source_added_event() -> None:
    uid, rid = _seed_report()
    with SessionLocal() as db:
        source, _ = sources_service.create_source_from_candidate(
            db, user_id=uid, report_id=rid, candidate=_candidate()
        )
    with SessionLocal() as db:
        rows = db.execute(
            text(
                "SELECT event_type, metadata AS meta "
                "FROM report_events WHERE report_id = :r"
            ),
            {"r": rid},
        ).all()
    assert len(rows) == 1
    assert rows[0].event_type == "source_added"
    meta = rows[0].meta
    assert meta["source_id"] == str(source.id)
    assert meta["source_api"] == "semantic_scholar"
    assert meta["external_source_id"] == "P1"
    assert "api_key" not in meta
    assert "raw" not in meta

def test_create_duplicate_is_idempotent() -> None:
    uid, rid = _seed_report()
    with SessionLocal() as db:
        s1, c1 = sources_service.create_source_from_candidate(
            db, user_id=uid, report_id=rid, candidate=_candidate()
        )
    with SessionLocal() as db:
        s2, c2 = sources_service.create_source_from_candidate(
            db, user_id=uid, report_id=rid, candidate=_candidate()
        )
    assert c1 is True
    assert c2 is False
    assert s1.id == s2.id
    with SessionLocal() as db:
        cnt = db.execute(
            text(
                "SELECT count(*) FROM report_events "
                "WHERE report_id = :r AND event_type = 'source_added'"
            ),
            {"r": rid},
        ).scalar()
    assert cnt == 1


def test_create_foreign_report_raises() -> None:
    _, rid_a = _seed_report()
    uid_b, _ = _seed_report()
    with SessionLocal() as db, pytest.raises(exc.ReportNotFound):
        sources_service.create_source_from_candidate(
            db, user_id=uid_b, report_id=rid_a, candidate=_candidate()
        )


def test_create_event_failure_rolls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uid, rid = _seed_report()

    def _fail(*_a: object, **_k: object) -> None:
        raise RuntimeError("simulated event failure")

    monkeypatch.setattr(
        "app.services.sources.create_source_added_event", _fail
    )
    with SessionLocal() as db, pytest.raises(RuntimeError):
        sources_service.create_source_from_candidate(
            db, user_id=uid, report_id=rid, candidate=_candidate()
        )
    with SessionLocal() as db:
        cnt = db.execute(
            text("SELECT count(*) FROM sources WHERE report_id = :r"),
            {"r": rid},
        ).scalar()
    assert cnt == 0


# ---------------------------------------------------------------------------
# List / Get
# ---------------------------------------------------------------------------
def test_list_sources_only_own_report() -> None:
    uid, rid = _seed_report()
    with SessionLocal() as db:
        sources_service.create_source_from_candidate(
            db, user_id=uid, report_id=rid, candidate=_candidate(ext="P1")
        )
    with SessionLocal() as db:
        rows = sources_service.list_sources_for_report(
            db, user_id=uid, report_id=rid
        )
    assert len(rows) == 1


def test_get_source_under_wrong_report_raises() -> None:
    with SessionLocal() as db:
        uid = db.execute(
            text(
                "INSERT INTO users (email, password_hash) "
                "VALUES (:e, 'h') RETURNING id"
            ),
            {"e": f"src-{uuid.uuid4().hex}@example.com"},
        ).scalar()
        rid_a = db.execute(
            text(
                "INSERT INTO reports "
                "(user_id, topic, status, output_language) "
                "VALUES (:u, 'A', 'draft', 'en') RETURNING id"
            ),
            {"u": uid},
        ).scalar()
        rid_b = db.execute(
            text(
                "INSERT INTO reports "
                "(user_id, topic, status, output_language) "
                "VALUES (:u, 'B', 'draft', 'en') RETURNING id"
            ),
            {"u": uid},
        ).scalar()
        db.commit()
    with SessionLocal() as db:
        source, _ = sources_service.create_source_from_candidate(
            db, user_id=uid, report_id=rid_a, candidate=_candidate()
        )
    with SessionLocal() as db, pytest.raises(exc.SourceNotFound):
        sources_service.get_source_for_report(
            db, user_id=uid, report_id=rid_b, source_id=source.id
        )
