"""Constraint-specific IntegrityError mapping."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import DetectionAlreadyCompletedError
from app.db.session import SessionLocal
from app.domain.detection import DetectionProviderResult
from app.services.detection import (
    _is_detection_identity_unique_violation,
    detect_report_version,
)
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


class _FakeOrig:
    def __init__(self, constraint_name: str) -> None:
        self.sqlstate = "23505"
        self.constraint_name = constraint_name


def _make_integrity_error(constraint: str) -> IntegrityError:
    return IntegrityError("statement", {}, _FakeOrig(constraint))


def test_detection_identity_violation_recognized() -> None:
    exc = _make_integrity_error("ux_detection_runs_identity")
    assert _is_detection_identity_unique_violation(exc)


def test_other_unique_violation_not_recognized() -> None:
    exc = _make_integrity_error("users_email_key")
    assert not _is_detection_identity_unique_violation(exc)


def test_no_constraint_name_not_recognized() -> None:
    class _BareOrig:
        sqlstate = "23505"

    exc = IntegrityError("statement", {}, _BareOrig())
    assert not _is_detection_identity_unique_violation(exc)


def _seed() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        uid = db.execute(
            text(
                "INSERT INTO users (email, password_hash) "
                "VALUES (:e, 'h') RETURNING id"
            ),
            {"e": f"ur-{uuid.uuid4().hex}@example.com"},
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


def test_second_detection_raises_already_completed() -> None:
    uid, rid, vid = _seed()
    profile = get_current_detection_profile()

    with SessionLocal() as db:
        detect_report_version(
            db,
            user_id=uid,
            report_id=rid,
            version_id=vid,
            provider=_OkProvider(),
            profile=profile,
        )
    with SessionLocal() as db, pytest.raises(
        DetectionAlreadyCompletedError
    ):
        detect_report_version(
            db,
            user_id=uid,
            report_id=rid,
            version_id=vid,
            provider=_OkProvider(),
            profile=profile,
        )
