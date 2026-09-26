"""M37 Phase 2-A2 — UsageService tests.

Covers:
  * record_event validation
  * idempotency (same key returns same row; NULL key never dedupes)
  * period aggregation (UTC half-open month)
  * workspace / metric isolation
  * concurrency: duplicate idempotency_key -> exactly one row
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, func, select

from app.core.exceptions import (
    UsageInvalidMetric,
    UsageInvalidQuantity,
    UsageInvalidSourceType,
    UsageWorkspaceMissing,
)
from app.db.models.project import Project, ProjectEvent
from app.db.models.usage import UsageEvent
from app.db.models.user import User
from app.db.session import SessionLocal
from app.services import usage as usage_service
from app.services.workspaces import ensure_default_workspace
from tests._m37_cleanup import purge_test_users

# ==========================================================================
# Fixtures & helpers
# ==========================================================================

@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    uids: list[uuid.UUID] = []
    yield uids
    if not uids:
        return
    with SessionLocal() as db:
        pids = select(Project.id).where(Project.user_id.in_(uids))
        db.execute(
            delete(ProjectEvent).where(ProjectEvent.project_id.in_(pids))
        )
        db.execute(delete(Project).where(Project.user_id.in_(uids)))
        purge_test_users(db, uids)
        db.commit()


def _mk_user(uids: list[uuid.UUID]) -> uuid.UUID:
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(
            User(
                id=uid,
                email=f"usage-{uid.hex[:8]}@example.com",
                password_hash="x",
            )
        )
        db.commit()
    uids.append(uid)
    return uid


def _ws_for(uid: uuid.UUID) -> uuid.UUID:
    with SessionLocal() as db:
        ws = ensure_default_workspace(db, user_id=uid)
        db.commit()
        return ws.id


# ==========================================================================
# record_event — validation
# ==========================================================================

def test_record_event_invalid_metric(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)
    ws_id = _ws_for(uid)
    with SessionLocal() as db, pytest.raises(UsageInvalidMetric):
        usage_service.record_event(
            db, workspace_id=ws_id, metric="not_a_metric", quantity=1
        )


def test_record_event_invalid_quantity(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)
    ws_id = _ws_for(uid)
    with SessionLocal() as db, pytest.raises(UsageInvalidQuantity):
        usage_service.record_event(
            db, workspace_id=ws_id, metric="reports_created", quantity=0
        )
    with SessionLocal() as db, pytest.raises(UsageInvalidQuantity):
        usage_service.record_event(
            db, workspace_id=ws_id, metric="reports_created", quantity=-5
        )


def test_record_event_invalid_source_type(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)
    ws_id = _ws_for(uid)
    with SessionLocal() as db, pytest.raises(UsageInvalidSourceType):
        usage_service.record_event(
            db,
            workspace_id=ws_id,
            metric="reports_created",
            quantity=1,
            source_type="not_a_source_type",
        )


def test_record_event_workspace_required() -> None:
    with SessionLocal() as db, pytest.raises(UsageWorkspaceMissing):
        usage_service.record_event(
            db, workspace_id=None, metric="reports_created", quantity=1  # type: ignore[arg-type]
        )


# ==========================================================================
# record_event — happy path
# ==========================================================================

def test_record_event_persists_row(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)
    ws_id = _ws_for(uid)
    with SessionLocal() as db:
        ev = usage_service.record_event(
            db,
            workspace_id=ws_id,
            metric="reports_created",
            quantity=2,
            user_id=uid,
            source_type="report",
            source_id=uuid.uuid4(),
            metadata={"note": "test"},
        )
        db.commit()
        assert ev.id is not None
        assert ev.workspace_id == ws_id
        assert ev.metric == "reports_created"
        assert ev.quantity == 2
        assert ev.user_id == uid
        assert ev.source_type == "report"


# ==========================================================================
# idempotency
# ==========================================================================

def test_record_event_with_null_key_never_dedupes(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)
    ws_id = _ws_for(uid)
    with SessionLocal() as db:
        e1 = usage_service.record_event(
            db, workspace_id=ws_id, metric="reports_created", quantity=1
        )
        e2 = usage_service.record_event(
            db, workspace_id=ws_id, metric="reports_created", quantity=1
        )
        db.commit()
        assert e1.id != e2.id

    with SessionLocal() as db:
        count = db.execute(
            select(func.count()).select_from(UsageEvent).where(
                UsageEvent.workspace_id == ws_id,
                UsageEvent.metric == "reports_created",
            )
        ).scalar_one()
        assert count == 2


def test_record_event_same_key_returns_same_row(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)
    ws_id = _ws_for(uid)
    key = "op-1"

    with SessionLocal() as db:
        e1 = usage_service.record_event(
            db,
            workspace_id=ws_id,
            metric="reports_created",
            quantity=1,
            idempotency_key=key,
        )
        db.commit()
        e1_id = e1.id

    with SessionLocal() as db:
        e2 = usage_service.record_event(
            db,
            workspace_id=ws_id,
            metric="reports_created",
            quantity=1,
            idempotency_key=key,
        )
        db.commit()
        assert e2.id == e1_id

    with SessionLocal() as db:
        count = db.execute(
            select(func.count()).select_from(UsageEvent).where(
                UsageEvent.workspace_id == ws_id,
                UsageEvent.metric == "reports_created",
                UsageEvent.idempotency_key == key,
            )
        ).scalar_one()
        assert count == 1


def test_record_event_key_is_scoped_to_metric_and_workspace(
    cleanup_users: list[uuid.UUID],
) -> None:
    u1 = _mk_user(cleanup_users)
    u2 = _mk_user(cleanup_users)
    ws1 = _ws_for(u1)
    ws2 = _ws_for(u2)
    key = "shared-key"

    with SessionLocal() as db:
        e1 = usage_service.record_event(
            db,
            workspace_id=ws1,
            metric="reports_created",
            quantity=1,
            idempotency_key=key,
        )
        e2 = usage_service.record_event(
            db,
            workspace_id=ws1,
            metric="files_uploaded",
            quantity=1,
            idempotency_key=key,
        )
        e3 = usage_service.record_event(
            db,
            workspace_id=ws2,
            metric="reports_created",
            quantity=1,
            idempotency_key=key,
        )
        db.commit()
        assert len({e1.id, e2.id, e3.id}) == 3


def test_record_event_concurrent_same_key_only_one_row(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)
    ws_id = _ws_for(uid)
    key = "conc-key"

    def _attempt(_i: int) -> uuid.UUID:
        with SessionLocal() as db:
            ev = usage_service.record_event(
                db,
                workspace_id=ws_id,
                metric="reports_created",
                quantity=1,
                idempotency_key=key,
            )
            db.commit()
            return ev.id

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(_attempt, range(4)))

    assert len(set(ids)) == 1, ids

    with SessionLocal() as db:
        count = db.execute(
            select(func.count()).select_from(UsageEvent).where(
                UsageEvent.workspace_id == ws_id,
                UsageEvent.metric == "reports_created",
                UsageEvent.idempotency_key == key,
            )
        ).scalar_one()
        assert count == 1


# ==========================================================================
# period aggregation
# ==========================================================================

def test_period_bounds_utc_mid_month() -> None:
    ref = datetime(2026, 3, 15, 12, 30, tzinfo=UTC)
    start, end = usage_service.period_bounds_utc(ref)
    assert start == datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC)
    assert end == datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)


def test_period_bounds_utc_december_rollover() -> None:
    ref = datetime(2026, 12, 31, 23, 59, tzinfo=UTC)
    start, end = usage_service.period_bounds_utc(ref)
    assert start == datetime(2026, 12, 1, 0, 0, 0, tzinfo=UTC)
    assert end == datetime(2027, 1, 1, 0, 0, 0, tzinfo=UTC)


def test_get_period_usage_sums_within_window(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)
    ws_id = _ws_for(uid)

    with SessionLocal() as db:
        # Feb event
        usage_service.record_event(
            db,
            workspace_id=ws_id,
            metric="reports_created",
            quantity=5,
            occurred_at=datetime(2026, 2, 15, tzinfo=UTC),
        )
        # Mar events (2 rows, total 3)
        usage_service.record_event(
            db,
            workspace_id=ws_id,
            metric="reports_created",
            quantity=1,
            occurred_at=datetime(2026, 3, 5, tzinfo=UTC),
        )
        usage_service.record_event(
            db,
            workspace_id=ws_id,
            metric="reports_created",
            quantity=2,
            occurred_at=datetime(2026, 3, 20, tzinfo=UTC),
        )
        # April event (outside)
        usage_service.record_event(
            db,
            workspace_id=ws_id,
            metric="reports_created",
            quantity=10,
            occurred_at=datetime(2026, 4, 1, 0, 0, tzinfo=UTC),
        )
        db.commit()

    with SessionLocal() as db:
        total = usage_service.get_period_usage(
            db,
            workspace_id=ws_id,
            metric="reports_created",
            period_start=datetime(2026, 3, 1, tzinfo=UTC),
            period_end=datetime(2026, 4, 1, tzinfo=UTC),
        )
        assert total == 3  # 1 + 2, half-open [start, end)


def test_get_period_usage_half_open_boundary(
    cleanup_users: list[uuid.UUID],
) -> None:
    """The end boundary is exclusive."""
    uid = _mk_user(cleanup_users)
    ws_id = _ws_for(uid)
    with SessionLocal() as db:
        usage_service.record_event(
            db,
            workspace_id=ws_id,
            metric="reports_created",
            quantity=7,
            occurred_at=datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC),
        )
        db.commit()
    with SessionLocal() as db:
        total = usage_service.get_period_usage(
            db,
            workspace_id=ws_id,
            metric="reports_created",
            period_start=datetime(2026, 3, 1, tzinfo=UTC),
            period_end=datetime(2026, 4, 1, tzinfo=UTC),  # exclusive
        )
        assert total == 0


def test_get_period_usage_isolated_by_workspace(
    cleanup_users: list[uuid.UUID],
) -> None:
    u1 = _mk_user(cleanup_users)
    u2 = _mk_user(cleanup_users)
    ws1 = _ws_for(u1)
    ws2 = _ws_for(u2)

    with SessionLocal() as db:
        usage_service.record_event(
            db, workspace_id=ws1, metric="reports_created", quantity=3
        )
        usage_service.record_event(
            db, workspace_id=ws2, metric="reports_created", quantity=5
        )
        db.commit()

    with SessionLocal() as db:
        n1 = usage_service.get_current_period_usage(
            db, workspace_id=ws1, metric="reports_created"
        )
        n2 = usage_service.get_current_period_usage(
            db, workspace_id=ws2, metric="reports_created"
        )
        assert n1 == 3
        assert n2 == 5


def test_get_period_usage_isolated_by_metric(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)
    ws_id = _ws_for(uid)
    with SessionLocal() as db:
        usage_service.record_event(
            db, workspace_id=ws_id, metric="reports_created", quantity=2
        )
        usage_service.record_event(
            db, workspace_id=ws_id, metric="files_uploaded", quantity=9
        )
        db.commit()
    with SessionLocal() as db:
        assert usage_service.get_current_period_usage(
            db, workspace_id=ws_id, metric="reports_created"
        ) == 2
        assert usage_service.get_current_period_usage(
            db, workspace_id=ws_id, metric="files_uploaded"
        ) == 9


# ==========================================================================
# helper keys
# ==========================================================================

def test_key_helpers_are_deterministic() -> None:
    rid = uuid.uuid4()
    assert usage_service.report_created_key(rid) == f"report:{rid}"
    jid = uuid.uuid4()
    assert usage_service.job_enqueued_key(jid) == f"job:{jid}"
    fid = uuid.uuid4()
    assert usage_service.file_uploaded_key(fid) == f"file:{fid}"
