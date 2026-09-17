"""Concurrent commit=False version allocation is serialized."""
from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import text

from app.db.session import SessionLocal
from app.services.report_versions import create_report_version


def _seed() -> tuple[uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        uid = db.execute(text(
            "INSERT INTO users (email, password_hash) "
            "VALUES (:e, 'h') RETURNING id"
        ), {"e": f"va-{uuid.uuid4().hex}@example.com"}).scalar()
        rid = db.execute(text(
            "INSERT INTO reports "
            "(user_id, topic, status, output_language) "
            "VALUES (:u, 'T', 'draft', 'en') RETURNING id"
        ), {"u": uid}).scalar()
        db.commit()
    return uid, rid


def test_version_allocation_serialized() -> None:
    uid, rid = _seed()
    barrier = Barrier(2)

    def _insert():  # noqa: ANN202
        barrier.wait()
        with SessionLocal() as db:
            try:
                create_report_version(
                    db, user_id=uid, report_id=rid,
                    language="en", content="x", commit=False,
                )
                db.commit()
                return "ok"
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                return type(exc).__name__

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _insert(), range(2)))

    assert "ok" in results
    with SessionLocal() as db:
        versions = db.execute(text(
            "SELECT version_number FROM report_versions "
            "WHERE report_id = :r ORDER BY version_number"
        ), {"r": rid}).scalars().all()
    assert versions == sorted(set(versions))
