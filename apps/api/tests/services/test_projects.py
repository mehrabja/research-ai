"""M18-A — Project service tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select

from app.core.exceptions import ProjectNotFound
from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.db.models.user import User
from app.db.session import SessionLocal
from app.domain.project import (
    InvalidProjectPayloadError,
    InvalidProjectStatusTransitionError,
    ProjectStatus,
)
from app.services import projects as projects_service


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    user_ids: list[uuid.UUID] = []
    yield user_ids
    if not user_ids:
        return
    with SessionLocal() as db:
        project_ids = select(Project.id).where(Project.user_id.in_(user_ids))
        db.execute(
            delete(ProjectEvent).where(
                ProjectEvent.project_id.in_(project_ids)
            )
        )
        db.execute(delete(Report).where(Report.user_id.in_(user_ids)))
        db.execute(delete(Project).where(Project.user_id.in_(user_ids)))
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


def _mk_user(cleanup_users: list[uuid.UUID]) -> uuid.UUID:
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(
            User(
                id=uid,
                email=f"u-{uid.hex[:10]}@example.com",
                password_hash="x",
            )
        )
        db.commit()
    cleanup_users.append(uid)
    return uid


def test_create_project_minimal(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="Alpha")
        assert p.id is not None
        assert p.status == ProjectStatus.DRAFT.value
        assert p.research_questions == []
        assert p.hypotheses == []
        events = (
            db.execute(
                select(ProjectEvent).where(ProjectEvent.project_id == p.id)
            )
            .scalars()
            .all()
        )
        assert [e.event_type for e in events] == ["project_created"]


def test_create_project_rejects_empty_name(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db, pytest.raises(InvalidProjectPayloadError):
        projects_service.create_project(db, user_id=uid, name="   ")


def test_create_project_rejects_unknown_status(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db, pytest.raises(InvalidProjectPayloadError):
        projects_service.create_project(
            db, user_id=uid, name="A", status="bogus"
        )


def test_create_project_rejects_archived_status(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db, pytest.raises(InvalidProjectPayloadError):
        projects_service.create_project(
            db, user_id=uid, name="A", status=ProjectStatus.ARCHIVED.value
        )


def test_create_project_normalizes_lists(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db,
            user_id=uid,
            name="Alpha",
            research_questions=["  Q1  ", "", "Q2"],
            hypotheses=[" H1 "],
        )
        assert p.research_questions == ["Q1", "Q2"]
        assert p.hypotheses == ["H1"]


def test_get_project_wrong_user(cleanup_users):
    uid_a = _mk_user(cleanup_users)
    uid_b = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid_a, name="A")
        with pytest.raises(ProjectNotFound):
            projects_service.get_project(db, user_id=uid_b, project_id=p.id)


def test_list_projects_isolated_by_user(cleanup_users):
    uid_a = _mk_user(cleanup_users)
    uid_b = _mk_user(cleanup_users)
    with SessionLocal() as db:
        projects_service.create_project(db, user_id=uid_a, name="A1")
        projects_service.create_project(db, user_id=uid_a, name="A2")
        projects_service.create_project(db, user_id=uid_b, name="B1")
        rows_a, total_a = projects_service.list_projects(db, user_id=uid_a)
        rows_b, total_b = projects_service.list_projects(db, user_id=uid_b)
        assert total_a == 2 and total_b == 1
        assert {p.name for p, _ in rows_a} == {"A1", "A2"}
        assert {p.name for p, _ in rows_b} == {"B1"}


def test_update_project_omitted_field_no_op(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="A", description="hello"
        )
        projects_service.update_project(
            db, user_id=uid, project_id=p.id, updates={}
        )
        assert p.description == "hello"


def test_update_project_null_clears_field(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="A", description="hello"
        )
        projects_service.update_project(
            db,
            user_id=uid,
            project_id=p.id,
            updates={"description": None},
        )
        assert p.description is None


def test_update_project_records_event(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="A")
        projects_service.update_project(
            db,
            user_id=uid,
            project_id=p.id,
            updates={"name": "B", "research_questions": ["Q"]},
        )
        events = (
            db.execute(
                select(ProjectEvent).where(
                    ProjectEvent.project_id == p.id,
                    ProjectEvent.event_type == "project_updated",
                )
            )
            .scalars()
            .all()
        )
        assert len(events) == 1
        assert events[0].event_meta["fields"] == [
            "name",
            "research_questions",
        ]


def test_update_archived_project_rejected(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="A")
        projects_service.archive_project(db, user_id=uid, project_id=p.id)
        with pytest.raises(InvalidProjectStatusTransitionError):
            projects_service.update_project(
                db, user_id=uid, project_id=p.id, updates={"name": "B"}
            )


def test_illegal_transition_rejected(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="A", status=ProjectStatus.ACTIVE.value
        )
        with pytest.raises(InvalidProjectStatusTransitionError):
            projects_service.update_project(
                db,
                user_id=uid,
                project_id=p.id,
                updates={"status": ProjectStatus.DRAFT.value},
            )


def test_archive_is_idempotent(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="A")
        a1 = projects_service.archive_project(db, user_id=uid, project_id=p.id)
        first = a1.archived_at
        a2 = projects_service.archive_project(db, user_id=uid, project_id=p.id)
        assert a1.status == a2.status == ProjectStatus.ARCHIVED.value
        assert a2.archived_at == first
        events = (
            db.execute(
                select(ProjectEvent).where(
                    ProjectEvent.project_id == p.id,
                    ProjectEvent.event_type == "project_archived",
                )
            )
            .scalars()
            .all()
        )
        assert len(events) == 1  # no duplicate on idempotent call


def test_count_project_reports_ignores_deleted(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="A")
        live = Report(
            user_id=uid,
            project_id=p.id,
            topic="live",
            output_language="en",
            status="draft",
        )
        dead = Report(
            user_id=uid,
            project_id=p.id,
            topic="dead",
            output_language="en",
            status="draft",
            deleted_at=datetime.now(UTC),
        )
        db.add_all([live, dead])
        db.commit()
        assert (
            projects_service.count_project_reports(
                db, user_id=uid, project_id=p.id
            )
            == 1
        )
