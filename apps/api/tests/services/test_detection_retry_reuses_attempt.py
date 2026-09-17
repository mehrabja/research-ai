"""A retryable failure leaves one running row; retry reuses it."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from app.domain.detection import DetectionProviderResult
from app.integrations.detection.base import DetectionRateLimitError
from app.services.detection import detect_report_version
from app.services.detection_profile import (
    get_current_detection_profile,
)

_LONG_TEXT = (
    "This is a sufficiently long piece of text. "
    "It contains multiple complete sentences. "
    "Each sentence has several words in it. "
    "The detection provider requires enough characters. "
    "So we pad this text to exceed the minimum. "
    "This ensures the provider path is exercised. "
    "And the label classification is reached. "
    "Finally the test can assert on the outcome."
)


def _seed() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        uid = db.execute(
            text(
                "INSERT INTO users (email, password_hash) "
                "VALUES (:e, 'h') RETURNING id"
            ),
            {"e": f"rr-{uuid.uuid4().hex}@example.com"},
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
            {"r": rid, "c": _LONG_TEXT},
        ).scalar()
        db.commit()
    return uid, rid, vid


class _FlakyProvider:
    provider_name = "heuristic"
    model_name = "baseline-v1"

    def __init__(self) -> None:
        self.calls = 0

    def detect(self, *, text: str) -> DetectionProviderResult:
        self.calls += 1
        if self.calls == 1:
            raise DetectionRateLimitError("429")
        return DetectionProviderResult(
            provider=self.provider_name,
            model=self.model_name,
            probability=0.7,
            raw_label=None,
            details={},
            input_chars=len(text),
        )


def test_retry_reuses_same_attempt_row() -> None:
    uid, rid, vid = _seed()
    provider = _FlakyProvider()
    profile = get_current_detection_profile()

    with SessionLocal() as db, pytest.raises(DetectionRateLimitError):
        detect_report_version(
            db,
            user_id=uid,
            report_id=rid,
            version_id=vid,
            provider=provider,
            profile=profile,
        )

    with SessionLocal() as db:
        rows = db.execute(
            text(
                "SELECT id, status FROM detection_runs "
                "WHERE report_id = :r"
            ),
            {"r": rid},
        ).all()
    assert len(rows) == 1
    assert rows[0].status == "running"
    attempt_id = rows[0].id

    with SessionLocal() as db:
        detect_report_version(
            db,
            user_id=uid,
            report_id=rid,
            version_id=vid,
            provider=provider,
            profile=profile,
        )

    with SessionLocal() as db:
        rows = db.execute(
            text(
                "SELECT id, status FROM detection_runs "
                "WHERE report_id = :r"
            ),
            {"r": rid},
        ).all()
    assert len(rows) == 1
    assert rows[0].id == attempt_id
    assert rows[0].status == "completed"
    assert provider.calls == 2
