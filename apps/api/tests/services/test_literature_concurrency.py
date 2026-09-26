"""M23 — Concurrency tests.

Verifies that concurrent pipeline executions for the same project
produce at most one completed run, thanks to the advisory lock +
partial unique index.
"""
from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models.literature import (
    LiteratureIntelligenceRun,
    ProjectLiteratureItem,
)
from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.db.models.source import Source
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.services import projects as projects_service
from app.services.literature import pipeline


@pytest.fixture(autouse=True)
def _clear_settings() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    uids: list[uuid.UUID] = []
    yield uids
    if not uids:
        return
    with SessionLocal() as db:
        pids = select(Project.id).where(Project.user_id.in_(uids))
        db.execute(
            delete(LiteratureIntelligenceRun).where(
                LiteratureIntelligenceRun.project_id.in_(pids)
            )
        )
        db.execute(
            delete(ProjectLiteratureItem).where(
                ProjectLiteratureItem.project_id.in_(pids)
            )
        )
        rids = select(Report.id).where(Report.project_id.in_(pids))
        db.execute(delete(Source).where(Source.report_id.in_(rids)))
        db.execute(delete(Report).where(Report.project_id.in_(pids)))
        db.execute(
            delete(ProjectEvent).where(ProjectEvent.project_id.in_(pids))
        )
        db.execute(delete(Project).where(Project.user_id.in_(uids)))
        # M37: purge owned workspaces before deleting user
        db.execute(
            delete(Workspace).where(
                Workspace.owner_user_id.in_(uids)
            )
        )
        db.execute(delete(User).where(User.id.in_(uids)))
        db.commit()


def _mk_user(uids) -> uuid.UUID:
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(
            User(
                id=uid,
                email=f"lit-cc-{uid.hex[:8]}@e.com",
                password_hash="x",
            )
        )
        db.commit()
    uids.append(uid)
    return uid


def _mk_project_with_source(uid) -> uuid.UUID:
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        r = Report(
            user_id=uid,
            project_id=p.id,
            topic="R",
            output_language="en",
            status="draft",
        )
        db.add(r)
        db.flush()
        db.add(
            Source(
                report_id=r.id, title="T", status="metadata_only"
            )
        )
        db.commit()
        return p.id


def test_concurrent_pipeline_single_completed_run(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project_with_source(uid)

    errors: list = []

    def _run():
        try:
            with SessionLocal() as db:
                pipeline.run_literature_analysis(
                    db, user_id=uid, project_id=pid
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=_run) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], errors

    with SessionLocal() as db:
        rows = list(
            db.execute(
                select(LiteratureIntelligenceRun).where(
                    LiteratureIntelligenceRun.project_id == pid,
                    LiteratureIntelligenceRun.status == "completed",
                )
            ).scalars().all()
        )
    assert len(rows) == 1, (
        f"expected exactly 1 completed run, got {len(rows)}"
    )

    with SessionLocal() as db:
        items = list(
            db.execute(
                select(ProjectLiteratureItem).where(
                    ProjectLiteratureItem.project_id == pid
                )
            ).scalars().all()
        )
    # At most one row per (project_id, source_id) — enforced by unique
    # constraint, but let's assert it anyway.
    source_ids = [it.source_id for it in items]
    assert len(source_ids) == len(set(source_ids))
