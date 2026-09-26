"""M36 — worker dies mid-job simulation.

Verifies that a stale worker lease is reclaimed by another worker via
the existing durable queue, without duplicating state.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.models.jobs import Job
from app.db.session import SessionLocal
from app.services import jobs as jobs_service


def test_stale_processing_job_is_reclaimed() -> None:
    with SessionLocal() as db:
        job = Job(
            job_type="test_noop",
            payload={"mode": "success"},
            status="processing",
            attempt_count=1,
            max_attempts=3,
            worker_id="dead-worker",
            started_at=datetime.now(UTC),
            heartbeat_at=datetime.now(UTC)
            - timedelta(hours=2),
            available_at=datetime.now(UTC),
            idempotency_key=f"m36-stale-{uuid.uuid4()}",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id

    with SessionLocal() as db:
        n = jobs_service.reclaim_stale_jobs(db)
    assert n >= 1

    with SessionLocal() as db:
        row = db.execute(
            select(Job).where(Job.id == job_id)
        ).scalar_one()
        assert row.status in ("retrying", "failed")
        assert row.worker_id is None
        assert row.heartbeat_at is None
        # Clean up
        db.delete(row)
        db.commit()
