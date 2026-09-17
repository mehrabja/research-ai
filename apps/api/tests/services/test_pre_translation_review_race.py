"""M15 — Pre-translation human review race-condition tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.models.report import Report, ReportEvent, ReportVersion, ReviewEvent
from app.db.models.user import User
from app.db.session import SessionLocal
from app.main import app
from app.services import reviews as reviews_service
from app.services.rate_limit import set_login_rate_limiter

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
        db.execute(delete(ReviewEvent).where(ReviewEvent.report_id.in_(report_ids)))
        db.execute(delete(ReportEvent).where(ReportEvent.report_id.in_(report_ids)))
        db.execute(delete(ReportVersion).where(ReportVersion.report_id.in_(report_ids)))
        db.execute(delete(Report).where(Report.id.in_(report_ids)))
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


def _register(cleanup_users):
    email = f"u-{uuid.uuid4().hex[:12]}@example.com"
    pw = "very-strong-password-1234"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": pw})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    with SessionLocal() as db:
        u = db.execute(select(User).where(User.email == email)).scalar_one()
        cleanup_users.append(u.id)
        return u.id


def _seed(user_id, content="base"):
    with SessionLocal() as db:
        report = Report(
            user_id=user_id,
            topic="T",
            output_language="en",
            status="pre_translation_review",
        )
        db.add(report)
        db.flush()
        v = ReportVersion(
            report_id=report.id, version_number=1, language="en",
            content=content, created_by_user=False, change_type="humanized",
        )
        db.add(v)
        db.commit()
        return report.id, v.id


def test_concurrent_approve_single_transition(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid)

    def _approve():
        with SessionLocal() as db:
            try:
                reviews_service.approve_pre_translation_review(
                    db, user_id=uid, report_id=report_id, version_id=version_id,
                )
                return "ok"
            except Exception as exc:  # noqa: BLE001
                return f"{type(exc).__name__}"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _approve(), range(2)))

    with SessionLocal() as db:
        report = db.get(Report, report_id)
        assert report.status == "translating"
        approved_events = db.execute(
            select(ReviewEvent).where(
                ReviewEvent.report_id == report_id,
                ReviewEvent.action == "approved",
            )
        ).scalars().all()
        assert len(approved_events) == 1
    assert "ok" in results


def test_concurrent_edit_single_success(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid)

    def _edit(text):
        with SessionLocal() as db:
            try:
                reviews_service.edit_pre_translation_review(
                    db, user_id=uid, report_id=report_id,
                    version_id=version_id, content=text,
                )
                return "ok"
            except Exception as exc:  # noqa: BLE001
                return f"{type(exc).__name__}"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(_edit, ["edit A", "edit B"]))

    assert results.count("ok") == 1
    assert sum("Stale" in r or "stale" in r for r in results) == 1

    with SessionLocal() as db:
        edited_events = db.execute(
            select(ReviewEvent).where(
                ReviewEvent.report_id == report_id,
                ReviewEvent.action == "edited",
            )
        ).scalars().all()
        assert len(edited_events) == 1
        versions = db.execute(
            select(ReportVersion).where(ReportVersion.report_id == report_id)
        ).scalars().all()
        assert len(versions) == 2


def test_edit_vs_approve_consistent(cleanup_users):
    uid = _register(cleanup_users)
    report_id, version_id = _seed(uid)

    def _edit():
        with SessionLocal() as db:
            try:
                reviews_service.edit_pre_translation_review(
                    db, user_id=uid, report_id=report_id,
                    version_id=version_id, content="edited",
                )
                return "edit_ok"
            except Exception as exc:  # noqa: BLE001
                return f"edit_{type(exc).__name__}"

    def _approve():
        with SessionLocal() as db:
            try:
                reviews_service.approve_pre_translation_review(
                    db, user_id=uid, report_id=report_id, version_id=version_id,
                )
                return "approve_ok"
            except Exception as exc:  # noqa: BLE001
                return f"approve_{type(exc).__name__}"

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda f: f(), [_edit, _approve]))

    with SessionLocal() as db:
        report = db.get(Report, report_id)
        assert report.status in ("pre_translation_review", "translating")
