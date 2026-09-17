"""Insufficient text short-circuits before the provider."""
from __future__ import annotations

import uuid

from sqlalchemy import text

from app.db.session import SessionLocal
from app.domain.detection import (
    DetectionProfile,
    DetectionProviderResult,
)
from app.services.detection import detect_report_version


def _seed() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        uid = db.execute(
            text(
                "INSERT INTO users (email, password_hash) "
                "VALUES (:e, 'h') RETURNING id"
            ),
            {"e": f"ne-{uuid.uuid4().hex}@example.com"},
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
                "VALUES (:r, 1, 'en', 'tiny') RETURNING id"
            ),
            {"r": rid},
        ).scalar()
        db.commit()
    return uid, rid, vid


class _SpyProvider:
    provider_name = "spy"
    model_name = "spy"

    def __init__(self) -> None:
        self.calls = 0

    def detect(self, *, text: str) -> DetectionProviderResult:
        self.calls += 1
        raise AssertionError("provider must not be called")


def test_insufficient_text_skips_provider() -> None:
    uid, rid, vid = _seed()
    profile = DetectionProfile(
        provider="spy",
        model="spy",
        profile_version="t",
        minimum_text_chars=1000,
    )
    spy = _SpyProvider()
    with SessionLocal() as db:
        result = detect_report_version(
            db,
            user_id=uid,
            report_id=rid,
            version_id=vid,
            provider=spy,
            profile=profile,
        )
    assert spy.calls == 0
    assert result.label == "unknown"
    assert result.probability is None
    with SessionLocal() as db:
        row = db.execute(
            text(
                "SELECT status FROM detection_runs "
                "WHERE report_id = :r"
            ),
            {"r": rid},
        ).scalar()
    assert row == "completed"
