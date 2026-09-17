"""Race-boundary tests for M10."""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from sqlalchemy import select, text, update

from app.core.exceptions import (
    InvalidJobStateError,
    JobLeaseLostError,
)
from app.db.models.jobs import Job
from app.db.session import SessionLocal
from app.services.jobs import (
    cancel_job,
    claim_job,
    complete_job,
    enqueue_job,
    fail_job,
    heartbeat_job,
    reclaim_stale_jobs,
)


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
            {"e": f"race-{uuid.uuid4().hex}@example.com"},
        ).scalar()
        db.commit()
    return uid


def _enqueue_test_noop(
    *, uid: uuid.UUID, max_attempts: int = 3
) -> uuid.UUID:
    with SessionLocal() as db:
        result = enqueue_job(
            db,
            job_type="test_noop",
            payload={},
            idempotency_key=f"k-{uuid.uuid4()}",
            user_id=uid,
            max_attempts=max_attempts,
        )
        return result.job.id


def _claim_specific_job(
    *, job_id: uuid.UUID, worker_id: str
) -> bool:
    now = datetime.now(UTC)
    with SessionLocal() as db:
        row = db.execute(
            select(Job)
            .where(
                Job.id == job_id,
                Job.status.in_(("queued", "retrying")),
                Job.available_at <= now,
                Job.attempt_count < Job.max_attempts,
            )
            .with_for_update(skip_locked=True)
        ).scalar_one_or_none()
        if row is None:
            db.rollback()
            return False
        row.status = "processing"
        row.attempt_count = row.attempt_count + 1
        row.worker_id = worker_id
        row.started_at = now
        row.heartbeat_at = now
        row.completed_at = None
        row.failed_at = None
        db.commit()
        return True


def _make_processing_job(
    *, uid: uuid.UUID, max_attempts: int = 3
) -> uuid.UUID:
    jid = _enqueue_test_noop(uid=uid, max_attempts=max_attempts)
    ok = _claim_specific_job(job_id=jid, worker_id="w-A")
    assert ok
    return jid


def _force_stale(*, job_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        db.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                heartbeat_at=datetime.now(UTC) - timedelta(hours=1)
            )
        )
        db.commit()


def _get_job(job_id: uuid.UUID) -> Job:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        assert job is not None
        db.expunge(job)
        return job


def test_heartbeat_fails_after_stale_reclaim() -> None:
    uid = _mk_user()
    jid = _make_processing_job(uid=uid)
    _force_stale(job_id=jid)

    with SessionLocal() as db:
        n = reclaim_stale_jobs(db)
    assert n == 1

    with SessionLocal() as db:
        ok = heartbeat_job(db, job_id=jid, worker_id="w-A")
    assert ok is False
    assert _get_job(jid).status == "retrying"


def test_complete_fails_after_stale_reclaim() -> None:
    uid = _mk_user()
    jid = _make_processing_job(uid=uid)
    _force_stale(job_id=jid)

    with SessionLocal() as db:
        reclaim_stale_jobs(db)

    with SessionLocal() as db, pytest.raises(JobLeaseLostError):
        complete_job(db, job_id=jid, worker_id="w-A")

    assert _get_job(jid).status == "retrying"


def test_fail_fails_after_stale_reclaim() -> None:
    uid = _mk_user()
    jid = _make_processing_job(uid=uid)
    _force_stale(job_id=jid)

    with SessionLocal() as db:
        reclaim_stale_jobs(db)

    with SessionLocal() as db, pytest.raises(JobLeaseLostError):
        fail_job(
            db,
            job_id=jid,
            worker_id="w-A",
            error_code="provider_unavailable",
            error_message="late failure",
        )
    assert _get_job(jid).status == "retrying"


def test_cancel_then_claim_leaves_cancelled() -> None:
    uid = _mk_user()
    jid = _enqueue_test_noop(uid=uid)

    with SessionLocal() as db:
        cancel_job(db, job_id=jid, user_id=uid)

    claimed = _claim_specific_job(job_id=jid, worker_id="w-A")
    assert claimed is False
    assert _get_job(jid).status == "cancelled"


def test_claim_then_cancel_raises_state_error() -> None:
    uid = _mk_user()
    jid = _make_processing_job(uid=uid)

    with SessionLocal() as db, pytest.raises(InvalidJobStateError):
        cancel_job(db, job_id=jid, user_id=uid)

    assert _get_job(jid).status == "processing"


def test_concurrent_cancel_and_claim_resolves_to_legal_state() -> None:
    uid = _mk_user()
    jid = _enqueue_test_noop(uid=uid)

    barrier = Barrier(2)

    def _cancel():  # noqa: ANN202
        barrier.wait()
        with SessionLocal() as db:
            try:
                cancel_job(db, job_id=jid, user_id=uid)
                return "cancelled"
            except InvalidJobStateError:
                return "conflict"

    def _claim():  # noqa: ANN202
        barrier.wait()
        with SessionLocal() as db:
            try:
                job = claim_job(db, worker_id="w-A")
                return "claimed" if job is not None else "none"
            except InvalidJobStateError:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_cancel)
        f2 = pool.submit(_claim)
        r_cancel = f1.result()
        r_claim = f2.result()

    final = _get_job(jid).status
    assert final in ("cancelled", "processing")
    assert not (r_cancel == "cancelled" and r_claim == "claimed")


def test_concurrent_complete_and_reclaim_keeps_state_valid() -> None:
    uid = _mk_user()
    jid = _make_processing_job(uid=uid)
    _force_stale(job_id=jid)

    barrier = Barrier(2)

    def _complete():  # noqa: ANN202
        barrier.wait()
        with SessionLocal() as db:
            try:
                complete_job(db, job_id=jid, worker_id="w-A")
                return "completed"
            except JobLeaseLostError:
                return "lease_lost"

    def _reclaim():  # noqa: ANN202
        barrier.wait()
        with SessionLocal() as db:
            return reclaim_stale_jobs(db)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_complete)
        f2 = pool.submit(_reclaim)
        r_complete = f1.result()
        _ = f2.result()

    final = _get_job(jid).status
    assert final in ("completed", "retrying", "failed")
    if r_complete == "completed":
        assert final == "completed"
    else:
        assert final in ("retrying", "failed")


def test_concurrent_heartbeat_and_reclaim_never_restores_lease() -> None:
    uid = _mk_user()
    jid = _make_processing_job(uid=uid)
    _force_stale(job_id=jid)

    barrier = Barrier(2)

    def _hb():  # noqa: ANN202
        barrier.wait()
        with SessionLocal() as db:
            return heartbeat_job(db, job_id=jid, worker_id="w-A")

    def _reclaim():  # noqa: ANN202
        barrier.wait()
        with SessionLocal() as db:
            return reclaim_stale_jobs(db)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_hb = pool.submit(_hb)
        f_rc = pool.submit(_reclaim)
        _ = f_hb.result()
        _ = f_rc.result()

    final = _get_job(jid)
    if final.status == "retrying":
        assert final.worker_id is None
        with SessionLocal() as db:
            ok = heartbeat_job(db, job_id=jid, worker_id="w-A")
        assert ok is False
    elif final.status == "processing":
        assert final.worker_id == "w-A"
    else:
        raise AssertionError(f"unexpected status: {final.status}")


def test_attempt_never_exceeds_max_after_stale() -> None:
    uid = _mk_user()
    jid = _make_processing_job(uid=uid, max_attempts=1)
    _force_stale(job_id=jid)

    with SessionLocal() as db:
        reclaim_stale_jobs(db)

    job = _get_job(jid)
    assert job.status == "failed"
    assert job.attempt_count == 1 == job.max_attempts
