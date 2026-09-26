"""M16 — Translation race-condition tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.models.ops import UsageLog
from app.db.models.pipeline import TranslationRun, TranslationVersion
from app.db.models.report import Report, ReportEvent, ReportVersion, ReviewEvent
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.integrations.translation.base import TranslationProviderResult
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
        # M37: purge owned workspaces before deleting user
        db.execute(
            delete(Workspace).where(
                Workspace.owner_user_id.in_(user_ids)
            )
        )
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


def _register(cleanup_users):
    email = f"u-{uuid.uuid4().hex[:12]}@example.com"
    pw = "very-strong-password-1234"
    r = client.post(
        "/api/v1/auth/register", json={"email": email, "password": pw}
    )
    assert r.status_code == 201
    r = client.post(
        "/api/v1/auth/login", json={"email": email, "password": pw}
    )
    assert r.status_code == 200
    with SessionLocal() as db:
        u = db.execute(select(User).where(User.email == email)).scalar_one()
        cleanup_users.append(u.id)
        return u.id


def _seed(uid):
    with SessionLocal() as db:
        report = Report(
            user_id=uid,
            topic="T",
            output_language="fa",
            status="translating",
        )
        db.add(report)
        db.flush()
        v = ReportVersion(
            report_id=report.id,
            version_number=1,
            language="en",
            content="Hello [E1] world 42%.",
            created_by_user=False,
            change_type="humanized",
        )
        db.add(v)
        db.flush()
        db.add(
            ReviewEvent(
                report_id=report.id,
                stage="pre_translation",
                user_id=uid,
                action="approved",
                version_id=v.id,
                notes=None,
            )
        )
        db.commit()
        return report.id, v.id


def _profile() -> TranslationProfile:
    return TranslationProfile(
        provider="fake",
        model="fake-model",
        temperature=0.1,
        max_output_tokens=1000,
        timeout_seconds=30.0,
        max_retries=0,
        retry_base_seconds=0.1,
        retry_max_seconds=1.0,
        retry_jitter_fraction=0.0,
        max_input_chars=10_000,
        max_output_chars=50_000,
        preservation_retry_count=0,
        profile_version="test.1",
    )


class _CountingProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def __init__(self):
        self.calls = 0

    def translate(self, **_kw) -> TranslationProviderResult:
        self.calls += 1
        return TranslationProviderResult(
            translated_text="ترجمه [E1] دنیا 42%.",
            provider=self.provider_name,
            model=self.model_name,
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            request_id="r",
        )


def test_concurrent_translation_single_success(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid)
    provider = _CountingProvider()

    def _run():
        with SessionLocal() as db:
            try:
                translation_service.translate_report(
                    db=db,
                    user_id=uid,
                    report_id=report_id,
                    source_version_id=version_id,
                    target_language="fa",
                    provider=provider,
                    profile=_profile(),
                )
                return "ok"
            except translation_service.TranslationAlreadySucceeded:
                return "already"
            except Exception as exc:  # noqa: BLE001
                return f"err:{type(exc).__name__}"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _run(), range(2)))

    ok_count = sum(1 for r in results if r == "ok")
    assert ok_count >= 1

    with SessionLocal() as db:
        report = db.get(Report, report_id)
        assert report.status == "post_translation_review"

        runs = db.execute(
            select(TranslationRun).where(TranslationRun.report_id == report_id)
        ).scalars().all()
        assert len([r for r in runs if r.status == "success"]) == 1

        versions = db.execute(
            select(TranslationVersion).where(
                TranslationVersion.translation_run_id.in_(
                    [r.id for r in runs]
                )
            )
        ).scalars().all()
        assert len(versions) == 1
