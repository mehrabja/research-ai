"""M16 — Translation service tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.models.ops import UsageLog
from app.db.models.pipeline import TranslationRun, TranslationVersion
from app.db.models.report import Report, ReportEvent, ReportVersion, ReviewEvent
from app.db.models.user import User
from app.db.session import SessionLocal
from app.integrations.translation.base import (
    TranslationAuthenticationError,
    TranslationProviderResult,
    TranslationRateLimitError,
)
from app.main import app
from app.services import translation as translation_service
from app.services.rate_limit import set_login_rate_limiter
from app.services.translation_profile import TranslationProfile

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_rate_limiter() -> Iterator[None]:
    set_login_rate_limiter(None)
    yield
    set_login_rate_limiter(None)


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    user_ids: list[uuid.UUID] = []
    yield user_ids
    if not user_ids:
        return
    with SessionLocal() as db:
        report_ids = select(Report.id).where(Report.user_id.in_(user_ids))
        run_ids = select(TranslationRun.id).where(
            TranslationRun.report_id.in_(report_ids)
        )
        db.execute(
            delete(UsageLog).where(UsageLog.report_id.in_(report_ids))
        )
        db.execute(
            delete(TranslationVersion).where(
                TranslationVersion.translation_run_id.in_(run_ids)
            )
        )
        db.execute(
            delete(TranslationRun).where(
                TranslationRun.report_id.in_(report_ids)
            )
        )
        db.execute(
            delete(ReviewEvent).where(ReviewEvent.report_id.in_(report_ids))
        )
        db.execute(
            delete(ReportEvent).where(ReportEvent.report_id.in_(report_ids))
        )
        db.execute(
            delete(ReportVersion).where(
                ReportVersion.report_id.in_(report_ids)
            )
        )
        db.execute(delete(Report).where(Report.id.in_(report_ids)))
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


def _register(cleanup_users):
    email = f"u-{uuid.uuid4().hex[:12]}@example.com"
    pw = "very-strong-password-1234"
    r = client.post(
        "/api/v1/auth/register", json={"email": email, "password": pw}
    )
    assert r.status_code == 201, r.text
    r = client.post(
        "/api/v1/auth/login", json={"email": email, "password": pw}
    )
    assert r.status_code == 200, r.text
    with SessionLocal() as db:
        u = db.execute(select(User).where(User.email == email)).scalar_one()
        cleanup_users.append(u.id)
        return u.id


def _seed(
    uid,
    *,
    source_lang: str = "en",
    target_lang: str = "fa",
    content: str = "Hello [E1] world 42%.",
    report_status: str = "translating",
):
    with SessionLocal() as db:
        report = Report(
            user_id=uid,
            topic="T",
            output_language=target_lang,
            status=report_status,
        )
        db.add(report)
        db.flush()
        version = ReportVersion(
            report_id=report.id,
            version_number=1,
            language=source_lang,
            content=content,
            created_by_user=False,
            change_type="humanized",
        )
        db.add(version)
        db.flush()
        db.add(
            ReviewEvent(
                report_id=report.id,
                stage="pre_translation",
                user_id=uid,
                action="approved",
                version_id=version.id,
                notes=None,
            )
        )
        db.commit()
        return report.id, version.id


def _profile(**overrides) -> TranslationProfile:
    base: dict = {
        "provider": "fake",
        "model": "fake-model",
        "temperature": 0.1,
        "max_output_tokens": 1000,
        "timeout_seconds": 30.0,
        "max_retries": 0,
        "retry_base_seconds": 0.1,
        "retry_max_seconds": 1.0,
        "retry_jitter_fraction": 0.0,
        "max_input_chars": 10_000,
        "max_output_chars": 50_000,
        "preservation_retry_count": 0,
        "profile_version": "test.1",
    }
    base.update(overrides)
    return TranslationProfile(**base)


class _FakeProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def translate(
        self,
        *,
        source_text: str,
        source_language: str,
        target_language: str,
        instructions: str,
        temperature: float,
        max_output_tokens: int,
    ) -> TranslationProviderResult:
        self.calls.append(
            {
                "source_text": source_text,
                "source_language": source_language,
                "target_language": target_language,
            }
        )
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return TranslationProviderResult(
            translated_text=item,
            provider=self.provider_name,
            model=self.model_name,
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            request_id="req-1",
        )


def test_translate_success(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid)
    provider = _FakeProvider(["ترجمه [E1] دنیا 42%."])

    with SessionLocal() as db:
        outcome = translation_service.translate_report(
            db=db,
            user_id=uid,
            report_id=report_id,
            source_version_id=version_id,
            target_language="fa",
            provider=provider,
            profile=_profile(),
        )
    assert outcome.status == "success"
    assert outcome.target_language == "fa"

    with SessionLocal() as db:
        report = db.get(Report, report_id)
        assert report.status == "post_translation_review"

        run = db.get(TranslationRun, outcome.run_id)
        assert run.status == "success"
        assert run.source_version_id == version_id

        tv = db.get(TranslationVersion, outcome.version_id)
        assert tv.content == "ترجمه [E1] دنیا 42%."
        assert tv.preservation_check_status == "passed"


def test_same_language_fails(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid, source_lang="en", target_lang="en")
    provider = _FakeProvider([])

    with SessionLocal() as db, pytest.raises(
        translation_service.TranslationValidationError
    ):
        translation_service.translate_report(
            db=db,
            user_id=uid,
            report_id=report_id,
            source_version_id=version_id,
            target_language="en",
            provider=provider,
            profile=_profile(),
        )

    with SessionLocal() as db:
        report = db.get(Report, report_id)
        assert report.status == "failed"

    assert provider.calls == []


def test_wrong_approved_version(cleanup_users):
    uid = _register(cleanup_users)
    report_id, _v1 = _seed(uid)

    with SessionLocal() as db:
        v2 = ReportVersion(
            report_id=report_id,
            version_number=2,
            language="en",
            content="Unapproved.",
            created_by_user=True,
            change_type="human_review_edit",
        )
        db.add(v2)
        db.commit()
        v2_id = v2.id

    provider = _FakeProvider([])
    with SessionLocal() as db, pytest.raises(
        translation_service.TranslationValidationError
    ):
        translation_service.translate_report(
            db=db,
            user_id=uid,
            report_id=report_id,
            source_version_id=v2_id,
            target_language="fa",
            provider=provider,
            profile=_profile(),
        )


def test_preservation_failure_rejects(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid, content="Hello [E1] world 42%.")
    provider = _FakeProvider(["دنیا بدون هیچ مارکر."])

    with SessionLocal() as db, pytest.raises(
        translation_service.TranslationPreservationError
    ):
        translation_service.translate_report(
            db=db,
            user_id=uid,
            report_id=report_id,
            source_version_id=version_id,
            target_language="fa",
            provider=provider,
            profile=_profile(),
        )

    with SessionLocal() as db:
        report = db.get(Report, report_id)
        assert report.status == "failed"

        runs = db.execute(
            select(TranslationRun).where(TranslationRun.report_id == report_id)
        ).scalars().all()
        assert len(runs) == 1
        assert runs[0].status == "failed"


def test_already_succeeded(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid)
    provider = _FakeProvider(["ترجمه [E1] دنیا 42%."])

    with SessionLocal() as db:
        translation_service.translate_report(
            db=db,
            user_id=uid,
            report_id=report_id,
            source_version_id=version_id,
            target_language="fa",
            provider=provider,
            profile=_profile(),
        )

    with SessionLocal() as db, pytest.raises(
        translation_service.TranslationAlreadySucceeded
    ):
        translation_service.translate_report(
            db=db,
            user_id=uid,
            report_id=report_id,
            source_version_id=version_id,
            target_language="fa",
            provider=_FakeProvider([]),
            profile=_profile(),
        )


def test_retryable_error_propagates(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid)
    provider = _FakeProvider([TranslationRateLimitError("429")])

    with SessionLocal() as db, pytest.raises(TranslationRateLimitError):
        translation_service.translate_report(
            db=db,
            user_id=uid,
            report_id=report_id,
            source_version_id=version_id,
            target_language="fa",
            provider=provider,
            profile=_profile(),
        )

    with SessionLocal() as db:
        run = db.execute(
            select(TranslationRun).where(
                TranslationRun.report_id == report_id
            )
        ).scalar_one()
        assert run.status == "running"

        report = db.get(Report, report_id)
        assert report.status == "translating"


def test_authentication_error_permanent(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid)
    provider = _FakeProvider([TranslationAuthenticationError("401")])

    with SessionLocal() as db, pytest.raises(TranslationAuthenticationError):
        translation_service.translate_report(
            db=db,
            user_id=uid,
            report_id=report_id,
            source_version_id=version_id,
            target_language="fa",
            provider=provider,
            profile=_profile(),
        )

    with SessionLocal() as db:
        report = db.get(Report, report_id)
        assert report.status == "failed"

        run = db.execute(
            select(TranslationRun).where(
                TranslationRun.report_id == report_id
            )
        ).scalar_one()
        assert run.status == "failed"


def test_input_too_large_fails(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid, content="x" * 500)
    provider = _FakeProvider([])

    with SessionLocal() as db, pytest.raises(
        translation_service.TranslationValidationError
    ):
        translation_service.translate_report(
            db=db,
            user_id=uid,
            report_id=report_id,
            source_version_id=version_id,
            target_language="fa",
            provider=provider,
            profile=_profile(max_input_chars=100),
        )

    with SessionLocal() as db:
        report = db.get(Report, report_id)
        assert report.status == "translating"
    assert provider.calls == []
