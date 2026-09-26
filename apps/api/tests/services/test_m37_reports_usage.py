"""M37 Phase 2-A3 — report creation emits usage events."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, func, select

from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.db.models.usage import UsageEvent
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.services import projects as projects_service
from app.services import reports as reports_service
from app.services import usage as usage_service
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
                email=f"rep-usage-{uid.hex[:8]}@example.com",
                password_hash="x",
            )
        )
        db.commit()
    uids.append(uid)
    return uid


def _mk_report(uid: uuid.UUID, *, topic: str = "T") -> Report:
    with SessionLocal() as db:
        return reports_service.create_report(
            db,
            user_id=uid,
            data={"topic": topic, "output_language": "en"},
        )


def _mk_project(uid: uuid.UUID) -> Project:
    with SessionLocal() as db:
        return projects_service.create_project(
            db, user_id=uid, name="P"
        )


# ==========================================================================
# orphan report
# ==========================================================================

def test_create_orphan_report_emits_reports_created(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)
    report = _mk_report(uid, topic="orphan")

    with SessionLocal() as db:
        events = list(
            db.execute(
                select(UsageEvent).where(
                    UsageEvent.source_id == report.id,
                )
            ).scalars()
        )

    assert len(events) == 1
    e = events[0]
    assert e.metric == "reports_created"
    assert e.quantity == 1
    assert e.user_id == uid
    assert e.source_type == "report"
    assert e.idempotency_key == usage_service.report_created_key(
        report.id
    )


def test_create_orphan_report_provisions_default_workspace(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)

    with SessionLocal() as db:
        n_before = db.execute(
            select(func.count())
            .select_from(Workspace)
            .where(Workspace.owner_user_id == uid)
        ).scalar_one()
    assert n_before == 0

    _mk_report(uid)

    with SessionLocal() as db:
        n_after = db.execute(
            select(func.count())
            .select_from(Workspace)
            .where(Workspace.owner_user_id == uid)
        ).scalar_one()
    assert n_after == 1


def test_two_reports_two_distinct_usage_events(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)
    r1 = _mk_report(uid, topic="r1")
    r2 = _mk_report(uid, topic="r2")

    with SessionLocal() as db:
        events = list(
            db.execute(
                select(UsageEvent).where(
                    UsageEvent.source_id.in_([r1.id, r2.id])
                )
            ).scalars()
        )

    assert len(events) == 2
    keys = {e.idempotency_key for e in events}
    assert len(keys) == 2
    assert keys == {
        usage_service.report_created_key(r1.id),
        usage_service.report_created_key(r2.id),
    }


# ==========================================================================
# report attached to a project
# ==========================================================================

def test_create_report_with_project_uses_project_workspace(
    cleanup_users: list[uuid.UUID],
) -> None:
    uid = _mk_user(cleanup_users)
    project = _mk_project(uid)

    with SessionLocal() as db:
        report = reports_service.create_report(
            db,
            user_id=uid,
            data={
                "topic": "attached",
                "output_language": "en",
                "project_id": project.id,
            },
        )
        report_id = report.id

    with SessionLocal() as db:
        e = db.execute(
            select(UsageEvent).where(
                UsageEvent.source_id == report_id
            )
        ).scalar_one()

    assert e.workspace_id == project.workspace_id


# ==========================================================================
# rollback safety
# ==========================================================================

def test_usage_failure_rolls_back_report(
    cleanup_users: list[uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uid = _mk_user(cleanup_users)

    def _boom(*_a, **_kw):
        raise RuntimeError("simulated usage failure")

    monkeypatch.setattr(
        reports_service.usage_service, "record_event", _boom
    )

    with SessionLocal() as db, pytest.raises(RuntimeError):
        reports_service.create_report(
            db,
            user_id=uid,
            data={"topic": "should-rollback", "output_language": "en"},
        )

    with SessionLocal() as db:
        count = db.execute(
            select(func.count())
            .select_from(Report)
            .where(Report.user_id == uid)
        ).scalar_one()
    assert count == 0
