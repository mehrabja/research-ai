"""M37 Phase 2-G — reports.monthly quota tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.core.exceptions import QuotaExceeded
from app.db.models.plan import Plan
from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.db.models.subscription import Subscription
from app.db.models.user import User
from app.db.session import SessionLocal
from app.domain.plan import FEATURE_REPORTS_MONTHLY
from app.services import reports as reports_service
from app.services import usage as usage_service
from app.services.workspaces import ensure_default_workspace
from tests._m37_cleanup import purge_test_users


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    uids: list[uuid.UUID] = []
    yield uids
    if not uids:
        return
    with SessionLocal() as db:
        pids = select(Project.id).where(Project.user_id.in_(uids))
        db.execute(
            delete(ProjectEvent).where(
                ProjectEvent.project_id.in_(pids)
            )
        )
        db.execute(delete(Report).where(Report.user_id.in_(uids)))
        db.execute(delete(Project).where(Project.user_id.in_(uids)))
        purge_test_users(db, uids)
        db.commit()


def _mk_user(uids: list[uuid.UUID]) -> uuid.UUID:
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(
            User(
                id=uid,
                email=f"qrep-{uid.hex[:8]}@example.com",
                password_hash="x",
            )
        )
        db.commit()
    uids.append(uid)
    return uid


def _resolve_limit(uid: uuid.UUID) -> int:
    with SessionLocal() as db:
        ws = ensure_default_workspace(db, user_id=uid)
        plan = db.execute(
            select(Plan)
            .join(Subscription, Subscription.plan_id == Plan.id)
            .where(
                Subscription.workspace_id == ws.id,
                Subscription.status == "active",
            )
        ).scalar_one()
        from app.services.entitlements import get_limit
        limit = get_limit(
            db, plan_id=plan.id, feature=FEATURE_REPORTS_MONTHLY
        )
        db.commit()
        assert limit is not None
        return limit


def _mk_report(uid: uuid.UUID, topic: str) -> Report:
    with SessionLocal() as db:
        return reports_service.create_report(
            db,
            user_id=uid,
            data={"topic": topic, "output_language": "en"},
        )


def test_under_limit_creates_reports(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)
    limit = _resolve_limit(uid)
    for i in range(min(limit, 3)):
        _mk_report(uid, f"r{i}")


def test_over_limit_raises(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)
    limit = _resolve_limit(uid)
    for i in range(limit):
        _mk_report(uid, f"r{i}")
    with SessionLocal() as db, pytest.raises(QuotaExceeded) as ei:
        reports_service.create_report(
            db,
            user_id=uid,
            data={"topic": "overflow", "output_language": "en"},
        )
    assert ei.value.feature == FEATURE_REPORTS_MONTHLY
    assert ei.value.limit == limit
    assert ei.value.current == limit


def test_previous_month_does_not_count(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)
    limit = _resolve_limit(uid)
    with SessionLocal() as db:
        ws = ensure_default_workspace(db, user_id=uid)
        # Insert last-month usage directly
        usage_service.record_event(
            db,
            workspace_id=ws.id,
            metric="reports_created",
            quantity=limit + 5,
            occurred_at=datetime.now(UTC) - timedelta(days=60),
        )
        db.commit()
    # Current month is still empty -> should succeed
    _mk_report(uid, "this-month")


def test_concurrent_creates_respect_limit(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)
    limit = _resolve_limit(uid)

    def _attempt(i: int) -> str:
        with SessionLocal() as db:
            try:
                reports_service.create_report(
                    db,
                    user_id=uid,
                    data={
                        "topic": f"c{i}",
                        "output_language": "en",
                    },
                )
                return "ok"
            except QuotaExceeded:
                return "quota"
            except Exception as exc:  # noqa: BLE001
                return f"err:{type(exc).__name__}"

    n = limit + 2
    with ThreadPoolExecutor(max_workers=n) as pool:
        results = list(pool.map(_attempt, range(n)))

    ok = sum(1 for r in results if r == "ok")
    quota = sum(1 for r in results if r == "quota")
    assert ok == limit, results
    assert quota == n - limit, results
