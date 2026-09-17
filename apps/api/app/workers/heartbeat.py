"""Automatic heartbeat runner for a claimed job."""
from __future__ import annotations

import logging
import threading
import uuid

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services import jobs as jobs_service

logger = logging.getLogger(__name__)


class HeartbeatRunner:
    def __init__(self, *, job_id: uuid.UUID, worker_id: str) -> None:
        self._job_id = job_id
        self._worker_id = worker_id
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.lease_lost = False

    def start(self) -> None:
        interval = float(
            get_settings().job_heartbeat_interval_seconds
        )
        self._thread = threading.Thread(
            target=self._loop,
            args=(interval,),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(
                timeout=float(
                    get_settings().job_heartbeat_interval_seconds
                )
                + 1.0
            )

    def _loop(self, interval: float) -> None:
        while not self._stop.wait(interval):
            try:
                with SessionLocal() as db:
                    ok = jobs_service.heartbeat_job(
                        db,
                        job_id=self._job_id,
                        worker_id=self._worker_id,
                    )
                if not ok:
                    self.lease_lost = True
                    logger.warning(
                        "heartbeat_lease_lost job_id=%s worker_id=%s",
                        self._job_id,
                        self._worker_id,
                    )
                    return
            except Exception:
                logger.exception(
                    "heartbeat_failed job_id=%s", self._job_id
                )


__all__ = ["HeartbeatRunner"]
