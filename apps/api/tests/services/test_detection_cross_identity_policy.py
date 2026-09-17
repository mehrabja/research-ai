"""Cross-identity policy: at most one running DetectionRun per report."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.core.exceptions import InvalidJobStateError
from app.db.session import SessionLocal
from app.domain.detection import DetectionProviderResult
from app.integrations.detection.base import DetectionRateLimitError
from app.services.detection import detect_report_version
from app.services.detection_profile import (
    get_current_detection_profile,
)

# Each must exceed detection_minimum_text_chars (default 200).
# Both are ~300+ chars to leave a safe margin.
_LONG_TEXT_V1 = (
    "This is the first version of the document. "
    "It is intentionally long enough to exceed the minimum. "
    "The detection pipeline requires sufficient text. "
    "So we add several sentences here. "
    "Each sentence contains enough words. "
    "That way the provider is actually invoked. "
    "And the assertion can check the outcome."
)
_LONG_TEXT_V2 = (
    "This is the second version of the document. "
    "It differs from the first version in wording. "
    "But it is also long enough to exceed the minimum. "
    "The detection pipeline requires sufficient text. "
    "So we add several sentences here as well. "
    "Each sentence contains enough words. "
    "And the final assertion can check the outcome."
)


def _seed_report_with_two_versions() -> tuple[
    uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID
]:
    with SessionLocal() as db:
        uid = db.execute(
            text(
                "INSERT INTO users (email, password_hash) "
                "VALUES (:e, 'h') RETURNING id"
            ),
            {"e": f"xi-{uuid.uuid4().hex}@example.com"},
        ).scalar()
        rid = db.execute(
            text(
                "INSERT INTO reports "
                "(user_id, topic, status, output_language) "
                "VALUES (:u, 'T', 'review_1', 'en') RETURNING id"
            ),
            {"u": uid},
        ).scalar()
        v1 = db.execute(
            text(
                "INSERT INTO report_versions "
                "(report_id, version_number, language, content) "
                "VALUES (:r, 1, 'en', :c) RETURNING id"
            ),
            {"r": rid, "c": _LONG_TEXT_V1},
        ).scalar()
        v2 = db.execute(
            text(
                "INSERT INTO report_versions "
                "(report_id, version_number, language, content) "
                "VALUES (:r, 2, 'en', :c) RETURNING id"
            ),
            {"r": rid, "c": _LONG_TEXT_V2},
        ).scalar()
        db.commit()
    return uid, rid, v1, v2


class _OkProvider:
    provider_name = "heuristic"
    model_name = "baseline-v1"

    def detect(self, *, text: str) -> DetectionProviderResult:
        return DetectionProviderResult(
            provider=self.provider_name,
            model=self.model_name,
            probability=0.5,
            raw_label=None,
            details={},
            input_chars=len(text),
        )


class _RateLimitedProvider:
    provider_name = "heuristic"
    model_name = "baseline-v1"

    def detect(self, *, text: str) -> DetectionProviderResult:
        raise DetectionRateLimitError("429")


def test_detecting_report_rejects_other_identity() -> None:
    uid, rid, v1, v2 = _seed_report_with_two_versions()
    profile = get_current_detection_profile()

    # Simulate an in-flight worker for V1.
    with SessionLocal() as db:
        db.execute(
            text(
                "INSERT INTO detection_runs "
                "(report_id, version_id, scanned_text_version, "
                " provider, profile_id, input_hash, input_chars, "
                " status) "
                "VALUES (:r, :v, :v_text, 'heuristic', 'p', 'h', 10, "
                "        'running')"
            ),
            {"r": rid, "v": v1, "v_text": str(v1)},
        )
        db.execute(
            text(
                "UPDATE reports SET status = 'detecting' WHERE id = :r"
            ),
            {"r": rid},
        )
        db.commit()

    with SessionLocal() as db, pytest.raises(InvalidJobStateError):
        detect_report_version(
            db,
            user_id=uid,
            report_id=rid,
            version_id=v2,
            provider=_OkProvider(),
            profile=profile,
        )

    with SessionLocal() as db:
        running_count = db.execute(
            text(
                "SELECT COUNT(*) FROM detection_runs "
                "WHERE report_id = :r AND status = 'running'"
            ),
            {"r": rid},
        ).scalar()
    assert running_count == 1


def test_retry_same_identity_still_allowed() -> None:
    uid, rid, v1, _v2 = _seed_report_with_two_versions()
    profile = get_current_detection_profile()

    with SessionLocal() as db, pytest.raises(DetectionRateLimitError):
        detect_report_version(
            db,
            user_id=uid,
            report_id=rid,
            version_id=v1,
            provider=_RateLimitedProvider(),
            profile=profile,
        )

    with SessionLocal() as db:
        detect_report_version(
            db,
            user_id=uid,
            report_id=rid,
            version_id=v1,
            provider=_OkProvider(),
            profile=profile,
        )

    with SessionLocal() as db:
        rows = db.execute(
            text(
                "SELECT status FROM detection_runs "
                "WHERE report_id = :r AND version_id = :v"
            ),
            {"r": rid, "v": v1},
        ).all()
    assert len(rows) == 1
    assert rows[0].status == "completed"
