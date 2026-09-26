"""Worker health snapshot (M36).

Internal diagnostic function. NOT exposed via public API because the
repository has no admin/operator authorization concept yet. Call from
an internal operator tool or a future authenticated admin route.

Authoritative job state lives in the ``jobs`` table. Worker stats are
informational only.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.jobs import Job
from app.workers import stats as worker_stats


def collect_health(db: Session) -> dict[str, object]:
    queued = int(
        db.execute(
            select(func.count())
            .select_from(Job)
            .where(Job.status.in_(("queued", "retrying")))
        ).scalar_one()
    )
    processing = int(
        db.execute(
            select(func.count())
            .select_from(Job)
            .where(Job.status == "processing")
        ).scalar_one()
    )
    return {
        "queue": {
            "queued_or_retrying": queued,
            "processing": processing,
        },
        "workers": worker_stats.snapshot_all(),
    }


__all__ = ["collect_health"]
