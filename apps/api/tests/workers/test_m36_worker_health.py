"""M36 — worker health snapshot tests."""
from __future__ import annotations

from sqlalchemy import delete

from app.db.models.jobs import Job
from app.db.session import SessionLocal
from app.workers import stats as worker_stats
from app.workers.health import collect_health


def test_collect_health_returns_queue_and_workers() -> None:
    worker_stats.reset()
    worker_stats.register("test-worker-health")
    with SessionLocal() as db:
        # Remove any queued test noise to keep counts deterministic.
        db.execute(delete(Job).where(Job.job_type == "test_noop"))
        db.commit()
        snap = collect_health(db)

    assert "queue" in snap
    assert "workers" in snap
    q = snap["queue"]
    assert isinstance(q, dict)
    assert "queued_or_retrying" in q
    assert "processing" in q
    assert isinstance(snap["workers"], list)
