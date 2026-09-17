"""Concurrent identical source creation yields one row + one event."""
from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import text

from app.db.session import SessionLocal
from app.domain.source import SourceCandidate
from app.services import sources as sources_service


def _seed() -> tuple[uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        uid = db.execute(
            text(
                "INSERT INTO users (email, password_hash) "
                "VALUES (:e, 'h') RETURNING id"
            ),
            {"e": f"cc-{uuid.uuid4().hex}@example.com"},
        ).scalar()
        rid = db.execute(
            text(
                "INSERT INTO reports "
                "(user_id, topic, status, output_language) "
                "VALUES (:u, 'T', 'draft', 'en') RETURNING id"
            ),
            {"u": uid},
        ).scalar()
        db.commit()
    return uid, rid


def _candidate(ext: str = "P1") -> SourceCandidate:
    return SourceCandidate(
        source_api="semantic_scholar",
        external_source_id=ext,
        title="T",
    )


def test_concurrent_identical_create_yields_one_source() -> None:
    uid, rid = _seed()
    barrier = Barrier(2)

    def _run() -> tuple[str, object, object]:
        barrier.wait()
        with SessionLocal() as db:
            try:
                source, created = (
                    sources_service.create_source_from_candidate(
                        db,
                        user_id=uid,
                        report_id=rid,
                        candidate=_candidate(),
                    )
                )
                return ("ok", created, source.id)
            except Exception as exc:  # noqa: BLE001
                return (type(exc).__name__, None, None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _run(), range(2)))

    with SessionLocal() as db:
        sources_cnt = db.execute(
            text("SELECT count(*) FROM sources WHERE report_id = :r"),
            {"r": rid},
        ).scalar()
        events_cnt = db.execute(
            text(
                "SELECT count(*) FROM report_events "
                "WHERE report_id = :r AND event_type = 'source_added'"
            ),
            {"r": rid},
        ).scalar()

    assert sources_cnt == 1, results
    assert events_cnt == 1, results
    ids = {r[2] for r in results if r[2] is not None}
    assert len(ids) == 1, results


def test_concurrent_different_ids_yield_two_sources() -> None:
    uid, rid = _seed()
    barrier = Barrier(2)

    def _run(ext: str) -> str:
        barrier.wait()
        with SessionLocal() as db:
            try:
                sources_service.create_source_from_candidate(
                    db,
                    user_id=uid,
                    report_id=rid,
                    candidate=_candidate(ext),
                )
                return "ok"
            except Exception as exc:  # noqa: BLE001
                return type(exc).__name__

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(_run, ["P1", "P2"]))

    with SessionLocal() as db:
        cnt = db.execute(
            text("SELECT count(*) FROM sources WHERE report_id = :r"),
            {"r": rid},
        ).scalar()
    assert cnt == 2
