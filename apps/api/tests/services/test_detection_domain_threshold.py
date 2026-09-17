"""Domain-aware threshold selection."""
from __future__ import annotations

import uuid

from sqlalchemy import text

from app.db.session import SessionLocal
from app.domain.detection import DetectionProviderResult
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


def _seed_report(
    domain: str | None,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        uid = db.execute(
            text(
                "INSERT INTO users (email, password_hash) "
                "VALUES (:e, 'h') RETURNING id"
            ),
            {"e": f"dm-{uuid.uuid4().hex}@example.com"},
        ).scalar()
        rid = db.execute(
            text(
                "INSERT INTO reports "
                "(user_id, topic, status, output_language, domain) "
                "VALUES (:u, 'T', 'review_1', 'en', :d) RETURNING id"
            ),
            {"u": uid, "d": domain},
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


def _upsert_threshold(
    *,
    detector: str,
    domain: str,
    language: str,
    threshold: float,
) -> None:
    """DELETE then INSERT — matches the (detector, domain, language)
    unique constraint on detection_thresholds."""
    with SessionLocal() as db:
        db.execute(
            text(
                "DELETE FROM detection_thresholds "
                "WHERE detector = :d AND domain = :dm "
                "AND language = :l"
            ),
            {"d": detector, "dm": domain, "l": language},
        )
        db.execute(
            text(
                "INSERT INTO detection_thresholds "
                "(detector, domain, language, threshold, percentiles) "
                "VALUES (:d, :dm, :l, :t, NULL)"
            ),
            {
                "d": detector,
                "dm": domain,
                "l": language,
                "t": threshold,
            },
        )
        db.commit()


class _FixedProbProvider:
    provider_name = "heuristic"
    model_name = "baseline-v1"

    def __init__(self, probability: float) -> None:
        self._p = probability

    def detect(self, *, text: str) -> DetectionProviderResult:
        return DetectionProviderResult(
            provider=self.provider_name,
            model=self.model_name,
            probability=self._p,
            raw_label=None,
            details={},
            input_chars=len(text),
        )


def test_exact_domain_takes_priority_over_general() -> None:
    # general threshold = 0.9 would map 0.5 → "low"
    # biology threshold = 0.1 maps 0.5 → "medium"
    _upsert_threshold(
        detector="heuristic",
        domain="general",
        language="en",
        threshold=0.9,
    )
    _upsert_threshold(
        detector="heuristic",
        domain="biology",
        language="en",
        threshold=0.1,
    )

    uid, rid, vid = _seed_report(domain="biology")
    profile = get_current_detection_profile()

    with SessionLocal() as db:
        result = detect_report_version(
            db,
            user_id=uid,
            report_id=rid,
            version_id=vid,
            provider=_FixedProbProvider(0.5),
            profile=profile,
        )

    assert result.label == "medium"


def test_missing_exact_domain_falls_back_to_general() -> None:
    _upsert_threshold(
        detector="heuristic",
        domain="general",
        language="en",
        threshold=0.1,
    )

    uid, rid, vid = _seed_report(domain="unknown_domain_xyz")
    profile = get_current_detection_profile()

    with SessionLocal() as db:
        result = detect_report_version(
            db,
            user_id=uid,
            report_id=rid,
            version_id=vid,
            provider=_FixedProbProvider(0.5),
            profile=profile,
        )
    assert result.label == "medium"
