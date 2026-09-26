"""In-process worker statistics (M36).

Informational only. Authoritative job state remains in the database.

Per-job tracking: ``job_started`` / ``job_finished`` are keyed by job
ID. Duplicate finishes are idempotent — they cannot corrupt the active
count of a different in-flight job.
"""
from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


class WorkerStats:
    def __init__(self, worker_id: str) -> None:
        self.worker_id = worker_id
        self._lock = threading.Lock()
        now = _now()
        self._started_at = now
        self._last_heartbeat_at = now
        self._last_claim_at: datetime | None = None
        self._last_job_type: str | None = None
        self._active_job_ids: set[str] = set()
        self._completed_jobs = 0
        self._failed_jobs = 0
        self._reclaimed_jobs = 0

    def touch(self) -> None:
        with self._lock:
            self._last_heartbeat_at = _now()

    def job_started(self, job_id: str, job_type: str) -> None:
        with self._lock:
            if job_id in self._active_job_ids:
                return
            self._active_job_ids.add(job_id)
            self._last_claim_at = _now()
            self._last_job_type = job_type
            self._last_heartbeat_at = _now()

    def job_finished(self, job_id: str, status: str) -> None:
        """status ∈ {'completed', 'failed', 'lease_lost', 'unknown'}.

        Idempotent per job ID. Finishing an unknown or already-finished
        job is a no-op — counters and active set are unchanged.
        """
        with self._lock:
            if job_id not in self._active_job_ids:
                logger.debug(
                    "worker_stats_finish_unknown worker_id=%s "
                    "job_id=%s status=%s",
                    self.worker_id,
                    job_id,
                    status,
                )
                return
            self._active_job_ids.discard(job_id)
            if status == "completed":
                self._completed_jobs += 1
            elif status == "failed":
                self._failed_jobs += 1
            self._last_heartbeat_at = _now()

    def jobs_reclaimed(self, count: int) -> None:
        if count <= 0:
            return
        with self._lock:
            self._reclaimed_jobs += int(count)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "worker_id": self.worker_id,
                "started_at": self._started_at.isoformat(),
                "last_heartbeat_at": self._last_heartbeat_at.isoformat(),
                "last_claim_at": (
                    self._last_claim_at.isoformat()
                    if self._last_claim_at else None
                ),
                "last_job_type": self._last_job_type,
                "active_jobs": len(self._active_job_ids),
                "completed_jobs": self._completed_jobs,
                "failed_jobs": self._failed_jobs,
                "reclaimed_jobs": self._reclaimed_jobs,
            }


_registry: dict[str, WorkerStats] = {}
_registry_lock = threading.Lock()


def register(worker_id: str) -> WorkerStats:
    with _registry_lock:
        stats = _registry.get(worker_id)
        if stats is None:
            stats = WorkerStats(worker_id=worker_id)
            _registry[worker_id] = stats
        return stats


def get(worker_id: str) -> WorkerStats | None:
    with _registry_lock:
        return _registry.get(worker_id)


def snapshot_all() -> list[dict[str, object]]:
    with _registry_lock:
        stats_list = list(_registry.values())
    return [s.snapshot() for s in stats_list]


def reset() -> None:
    with _registry_lock:
        _registry.clear()


__all__ = [
    "WorkerStats",
    "get",
    "register",
    "reset",
    "snapshot_all",
]
