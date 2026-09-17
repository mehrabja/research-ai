"""Concurrency tests using independent sessions."""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from app.services.jobs import claim_job, enqueue_job


@pytest.fixture(autouse=True)
def _isolate_jobs() -> Iterator[None]:
    with SessionLocal() as db:
        db.execute(text("DELETE FROM jobs"))
        db.commit()
    yield
    with SessionLocal() as db:
        db.execute(text("DELETE FROM jobs"))
        db.commit()


def _mk_user() -> uuid.UUID:
    with SessionLocal() as db:
        uid = db.execute(
            text(
                "INSERT INTO users (email, password_hash) "
                "VALUES (:e, 'h') RETURNING id"
            ),
            {"e": f"conc-{uuid.uuid4().hex}@example.com"},
        ).scalar()
        db.commit()
    return uid


def test_one_job_one_claim() -> None:
    uid = _mk_user()
    with SessionLocal() as db:
        enqueue_job(
            db,
            job_type="test_noop",
            payload={"mode": "success"},
            idempotency_key=f"k-{uuid.uuid4()}",
            user_id=uid,
        )

    barrier = Barrier(4)

    def _worker(n: int):  # noqa: ANN202
        barrier.wait()
        with SessionLocal() as db:
            return claim_job(db, worker_id=f"w-{n}")

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(_worker, range(4)))

    claimed = [j for j in results if j is not None]
    assert len(claimed) == 1


def test_many_jobs_no_double_claim() -> None:
    uid = _mk_user()
    with SessionLocal() as db:
        for _ in range(8):
            enqueue_job(
                db,
                job_type="test_noop",
                payload={},
                idempotency_key=f"k-{uuid.uuid4()}",
                user_id=uid,
            )

    barrier = Barrier(4)

    def _worker(n: int):  # noqa: ANN202
        barrier.wait()
        claimed_ids = []
        while True:
            with SessionLocal() as db:
                job = claim_job(db, worker_id=f"w-{n}")
            if job is None:
                break
            claimed_ids.append(str(job.id))
        return claimed_ids

    with ThreadPoolExecutor(max_workers=4) as pool:
        per_worker = list(pool.map(_worker, range(4)))

    all_ids = [jid for sub in per_worker for jid in sub]
    assert len(all_ids) == len(set(all_ids))
    assert len(all_ids) == 8
