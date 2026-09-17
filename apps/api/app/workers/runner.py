"""Worker main loop."""
from __future__ import annotations

import logging
import os
import signal
import socket
import time
import uuid
from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.exceptions import JobLeaseLostError
from app.db.models.jobs import Job
from app.db.session import SessionLocal
from app.domain.jobs import JobContext
from app.services import jobs as jobs_service
from app.workers.classification import classify_exception
from app.workers.heartbeat import HeartbeatRunner
from app.workers.registry import HandlerNotFound, get_handler

logger = logging.getLogger(__name__)


def generate_worker_id() -> str:
    host = socket.gethostname() or "host"
    pid = os.getpid()
    suffix = uuid.uuid4().hex[:8]
    return f"{host}:{pid}:{suffix}"


class Worker:
    def __init__(self, *, worker_id: str | None = None) -> None:
        self._settings = get_settings()
        self.worker_id = worker_id or generate_worker_id()
        self._stopping = False
        self._last_recovery_at: datetime | None = None

    def install_signal_handlers(self) -> None:
        def _handler(signum, _frame):  # noqa: ANN001
            logger.info(
                "worker_shutdown_signal worker_id=%s signal=%s",
                self.worker_id,
                signum,
            )
            self._stopping = True

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)

    def run_forever(self) -> None:
        self.install_signal_handlers()
        logger.info("worker_started worker_id=%s", self.worker_id)

        while not self._stopping:
            self._maybe_recover()
            claimed = self._claim_once()
            if not claimed and not self._stopping:
                time.sleep(self._settings.job_poll_interval_seconds)

        logger.info("worker_stopped worker_id=%s", self.worker_id)

    def _maybe_recover(self) -> None:
        now = datetime.now(UTC)
        if self._last_recovery_at is not None:
            elapsed = (now - self._last_recovery_at).total_seconds()
            if elapsed < (
                self._settings.job_processing_timeout_seconds / 2
            ):
                return
        self._last_recovery_at = now
        try:
            with SessionLocal() as db:
                n = jobs_service.reclaim_stale_jobs(db)
            if n:
                logger.warning(
                    "stale_jobs_reclaimed count=%d worker_id=%s",
                    n,
                    self.worker_id,
                )
        except Exception:
            logger.exception("stale_recovery_failed")

    def _claim_once(self) -> bool:
        with SessionLocal() as db:
            job = jobs_service.claim_job(
                db, worker_id=self.worker_id
            )
        if job is None:
            return False
        self._execute(job)
        return True

    def _execute(self, job: Job) -> None:
        started = time.monotonic()
        try:
            handler = get_handler(job.job_type)
        except HandlerNotFound:
            self._finalize_failure(
                job_id=job.id,
                error_code="unknown_job_type",
                error_message=(
                    f"no handler for job_type={job.job_type!r}"
                ),
            )
            return

        heartbeat = HeartbeatRunner(
            job_id=job.id, worker_id=self.worker_id
        )
        heartbeat.start()
        try:
            ctx = JobContext(
                job_id=job.id,
                job_type=job.job_type,
                attempt_count=job.attempt_count,
                worker_id=self.worker_id,
                payload=dict(job.payload or {}),
            )
            handler(ctx)
        except Exception as exc:
            heartbeat.stop()
            code = classify_exception(exc)
            logger.warning(
                "job_handler_failed job_id=%s code=%s",
                job.id,
                code,
            )
            self._finalize_failure(
                job_id=job.id,
                error_code=code,
                error_message=type(exc).__name__,
            )
            return
        heartbeat.stop()

        if heartbeat.lease_lost:
            logger.warning(
                "lease_lost_skip_complete job_id=%s", job.id
            )
            return

        with SessionLocal() as db:
            try:
                jobs_service.complete_job(
                    db, job_id=job.id, worker_id=self.worker_id
                )
            except JobLeaseLostError:
                logger.warning(
                    "lease_lost_during_complete job_id=%s", job.id
                )
                return

        duration_ms = int((time.monotonic() - started) * 1000)
        logger.info(
            "job_completed job_id=%s job_type=%s duration_ms=%d",
            job.id,
            job.job_type,
            duration_ms,
        )

    def _finalize_failure(
        self,
        *,
        job_id: uuid.UUID,
        error_code: str,
        error_message: str,
    ) -> None:
        with SessionLocal() as db:
            try:
                jobs_service.fail_job(
                    db,
                    job_id=job_id,
                    worker_id=self.worker_id,
                    error_code=error_code,
                    error_message=error_message,
                )
            except JobLeaseLostError:
                logger.warning(
                    "lease_lost_during_fail job_id=%s", job_id
                )


def main() -> None:
    import logging as _logging

    from app.workers.handlers import register_all_handlers

    _logging.basicConfig(level=_logging.INFO)
    register_all_handlers()
    Worker().run_forever()


__all__ = ["Worker", "generate_worker_id", "main"]
