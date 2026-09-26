"""M27 — Service tests."""
from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.core.exceptions import ManuscriptResearchPlanMissing
from app.db.models.manuscript import (
    Manuscript,
    ManuscriptRun,
    ManuscriptSection,
    ManuscriptSectionDependency,
    ManuscriptVersion,
)
from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report, ReportEvent
from app.db.models.research_plan import (
    ResearchEvidenceRequirement,
    ResearchPlan,
    ResearchPlanDependency,
    ResearchPlanRun,
    ResearchPlanSection,
)
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.services import projects as projects_service
from app.services.manuscript import builder as builder_svc
from app.services.research_planning import planner as planner_svc


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
        rids = select(Report.id).where(Report.user_id.in_(uids))
        plan_ids = select(ResearchPlan.id).where(
            ResearchPlan.project_id.in_(pids)
        )
        version_ids = select(ManuscriptVersion.id).where(
            ManuscriptVersion.manuscript_id.in_(
                select(Manuscript.id).where(Manuscript.report_id.in_(rids))
            )
        )
        section_ids = select(ManuscriptSection.id).where(
            ManuscriptSection.manuscript_version_id.in_(version_ids)
        )

        # M27 — deepest children first
        db.execute(delete(ManuscriptSectionDependency).where(
            ManuscriptSectionDependency.manuscript_version_id.in_(version_ids)
        ))
        db.execute(delete(ManuscriptSection).where(
            ManuscriptSection.id.in_(section_ids)
        ))
        db.execute(delete(ManuscriptVersion).where(
            ManuscriptVersion.id.in_(version_ids)
        ))
        db.execute(delete(Manuscript).where(Manuscript.report_id.in_(rids)))
        db.execute(delete(ManuscriptRun).where(
            ManuscriptRun.report_id.in_(rids)
        ))

        # M24
        db.execute(delete(ResearchPlanRun).where(
            ResearchPlanRun.project_id.in_(pids)
        ))
        db.execute(delete(ResearchPlanDependency).where(
            ResearchPlanDependency.plan_id.in_(plan_ids)
        ))
        db.execute(delete(ResearchEvidenceRequirement).where(
            ResearchEvidenceRequirement.plan_id.in_(plan_ids)
        ))
        db.execute(delete(ResearchPlanSection).where(
            ResearchPlanSection.plan_id.in_(plan_ids)
        ))
        db.execute(delete(ResearchPlan).where(
            ResearchPlan.project_id.in_(pids)
        ))

        # Reports (must go before Projects AND before Users)
        db.execute(delete(ReportEvent).where(ReportEvent.report_id.in_(rids)))
        db.execute(delete(Report).where(Report.user_id.in_(uids)))

        # Projects + Users
        db.execute(delete(ProjectEvent).where(
            ProjectEvent.project_id.in_(pids)
        ))
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
        db.add(User(
            id=uid, email=f"ms-{uid.hex[:8]}@e.com", password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


def _mk_project(uid) -> uuid.UUID:
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        return p.id


def _mk_report(uid, pid) -> uuid.UUID:
    rid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(Report(
            id=rid, user_id=uid, project_id=pid,
            topic="A study of X", output_language="en",
        ))
        db.commit()
    return rid


def _ready_plan(uid, pid) -> uuid.UUID:
    with SessionLocal() as db:
        planner_svc.generate_research_plan(
            db, user_id=uid, project_id=pid
        )
    return pid


def test_generate_creates_ready_version(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    rid = _mk_report(uid, pid)
    _ready_plan(uid, pid)

    with SessionLocal() as db:
        result = builder_svc.generate_manuscript(
            db, user_id=uid, report_id=rid
        )
    assert result.skipped is False
    assert result.run.status == "completed"
    assert result.version is not None
    assert result.version.status == "ready"

    with SessionLocal() as db:
        n = db.execute(
            select(func.count()).select_from(ManuscriptSection).where(
                ManuscriptSection.manuscript_version_id == result.version.id
            )
        ).scalar_one()
    assert n >= 4


def test_idempotent_second_call_skips(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    rid = _mk_report(uid, pid)
    _ready_plan(uid, pid)

    with SessionLocal() as db:
        r1 = builder_svc.generate_manuscript(
            db, user_id=uid, report_id=rid
        )
    with SessionLocal() as db:
        r2 = builder_svc.generate_manuscript(
            db, user_id=uid, report_id=rid
        )
    assert r1.skipped is False
    assert r2.skipped is True

    with SessionLocal() as db:
        versions = db.execute(
            select(func.count()).select_from(ManuscriptVersion).where(
                ManuscriptVersion.manuscript_id == r1.manuscript.id
            )
        ).scalar_one()
        completed = db.execute(
            select(func.count()).select_from(ManuscriptRun).where(
                ManuscriptRun.report_id == rid,
                ManuscriptRun.status == "completed",
            )
        ).scalar_one()
    assert versions == 1
    assert completed == 1


def test_concurrent_generate_one_version(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    rid = _mk_report(uid, pid)
    _ready_plan(uid, pid)

    errors: list = []

    def _run():
        try:
            with SessionLocal() as db:
                builder_svc.generate_manuscript(
                    db, user_id=uid, report_id=rid
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=_run) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []

    with SessionLocal() as db:
        ms = db.execute(
            select(Manuscript).where(Manuscript.report_id == rid)
        ).scalar_one()
        n = db.execute(
            select(func.count()).select_from(ManuscriptVersion).where(
                ManuscriptVersion.manuscript_id == ms.id
            )
        ).scalar_one()
    assert n == 1


def test_missing_plan_fails_closed(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    rid = _mk_report(uid, pid)
    with SessionLocal() as db, pytest.raises(ManuscriptResearchPlanMissing):
        builder_svc.generate_manuscript(
            db, user_id=uid, report_id=rid
        )


def test_research_contract_present(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid = _mk_project(uid)
    rid = _mk_report(uid, pid)
    _ready_plan(uid, pid)
    with SessionLocal() as db:
        result = builder_svc.generate_manuscript(
            db, user_id=uid, report_id=rid
        )
    with SessionLocal() as db:
        rows = list(db.execute(
            select(ManuscriptSection).where(
                ManuscriptSection.manuscript_version_id == result.version.id
            )
        ).scalars().all())
    for s in rows:
        assert s.research_contract["section_key"] == s.section_key
        assert "retrieval_intents" in s.research_contract
        assert (
            s.research_contract["intent_mapping_version"]
            == "m27-intent-v1"
        )
