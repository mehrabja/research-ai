"""Two concurrent workers → one completed attempt (at-least-once)."""
from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import text

from app.db.session import SessionLocal
from app.domain.detection import (
    DetectionProviderResult,
    build_detection_profile_id,
    hash_detection_input,
)
from app.services.detection import detect_report_version
from app.services.detection_profile import (
    get_current_detection_profile,
)

# Must exceed detection_minimum_text_chars (default 200). ~340 chars.
_LONG_CONTENT = (
    "This is a sufficiently long piece of text. "
    "It contains multiple complete sentences. "
    "Each sentence has several words in it. "
    "The detection provider requires enough characters. "
    "So we pad this text to exceed the minimum. "
    "This ensures the provider path is exercised. "
    "And the label classification is reached. "
    "Finally the test can assert on the outcome."
)


def _seed() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, str]:
    content = _LONG_CONTENT
    with SessionLocal() as db:
        uid = db.execute(
            text(
                "INSERT INTO users (email, password_hash) "
                "VALUES (:e, 'h') RETURNING id"
            ),
            {"e": f"cn-{uuid.uuid4().hex}@example.com"},
        ).scalar()
        rid = db.execute(
            text(
                "INSERT INTO reports "
                "(user_id, topic, status, output_language) "
                "VALUES (:u, 'T', 'review_1', 'en') RETURNING id"
            ),
            {"u": uid},
        ).scalar()
        vid = db.execute(
            text(
                "INSERT INTO report_versions "
                "(report_id, version_number, language, content) "
                "VALUES (:r, 1, 'en', :c) RETURNING id"
            ),
            {"r": rid, "c": content},
        ).scalar()
        db.commit()
    return uid, rid, vid, content


class _CounterProvider:
    provider_name = "heuristic"
    model_name = "baseline-v1"

    def __init__(self) -> None:
        self.calls = 0
        self._lock = threading.Lock()

    def detect(self, *, text: str) -> DetectionProviderResult:
        with self._lock:
            self.calls += 1
        return DetectionProviderResult(
            provider=self.provider_name,
            model=self.model_name,
            probability=0.5,
            raw_label=None,
            details={},
            input_chars=len(text),
        )


def test_concurrent_detection_creates_one_attempt_row() -> None:
    uid, rid, vid, content = _seed()
    provider = _CounterProvider()
    profile = get_current_detection_profile()
    profile_id = build_detection_profile_id(profile)
    input_hash = hash_detection_input(content)

    barrier = Barrier(2)

    def _run() -> str:
        barrier.wait()
        with SessionLocal() as db:
            try:
                detect_report_version(
                    db,
                    user_id=uid,
                    report_id=rid,
                    version_id=vid,
                    provider=provider,
                    profile=profile,
                )
                return "ok"
            except Exception as exc:
                return type(exc).__name__

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: _run(), range(2)))

    with SessionLocal() as db:
        total_attempts = db.execute(
            text(
                "SELECT COUNT(*) FROM detection_runs "
                "WHERE report_id = :r AND version_id = :v "
                "AND profile_id = :p AND input_hash = :h"
            ),
            {"r": rid, "v": vid, "p": profile_id, "h": input_hash},
        ).scalar()
        completed = db.execute(
            text(
                "SELECT COUNT(*) FROM detection_runs "
                "WHERE report_id = :r AND version_id = :v "
                "AND status = 'completed'"
            ),
            {"r": rid, "v": vid},
        ).scalar()
        running = db.execute(
            text(
                "SELECT COUNT(*) FROM detection_runs "
                "WHERE report_id = :r AND status = 'running'"
            ),
            {"r": rid},
        ).scalar()

    assert completed == 1
    assert running == 0
    assert total_attempts == 1
    # At-least-once: provider may have been called twice.
    assert provider.calls in (1, 2)
