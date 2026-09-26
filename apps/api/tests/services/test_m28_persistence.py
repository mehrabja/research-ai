"""M28 — Persistence + idempotency tests (M26 mocked)."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, func, select

from app.core.config import get_settings
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
from app.db.models.section_research import (
    SectionResearchEvidence,
    SectionResearchRun,
)
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.services import projects as projects_service
from app.services.manuscript import builder as builder_svc
from app.services.research_planning import planner as planner_svc
from app.services.section_research import persistence as persist_svc


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
        run_ids = select(SectionResearchRun.id).where(
            SectionResearchRun.manuscript_section_id.in_(section_ids)
        )

        db.execute(delete(SectionResearchEvidence).where(
            SectionResearchEvidence.research_run_id.in_(run_ids)
        ))
        db.execute(delete(SectionResearchRun).where(
            SectionResearchRun.id.in_(run_ids)
        ))
        db.execute(delete(ManuscriptSectionDependency).where(
            ManuscriptSectionDependency.manuscript_version_id.in_(
                version_ids
            )
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

        db.execute(delete(ReportEvent).where(ReportEvent.report_id.in_(rids)))
        db.execute(delete(Report).where(Report.user_id.in_(uids)))

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


@pytest.fixture(autouse=True)
def _mock_m26_retrieval(monkeypatch) -> Iterator[None]:
    """M28 tests mock M26 to avoid needing a real retrieval corpus.

    Per M28 spec §32 and §36, M26 must be fake/mocked in unit/service
    tests. The mock returns run.id = None because no real
    retrieval_runs row is inserted; the persistence layer must
    accept a nullable retrieval_run_id.
    """
    from app.services.section_research import retrieval as ret_svc

    class _FakeRun:
        def __init__(self) -> None:
            self.id = None
            self.status = "completed"

    class _FakeOutcome:
        def __init__(self) -> None:
            self.run = _FakeRun()
            self.results: list[dict] = []
            self.coverage: dict | None = None
            self.warnings: list[str] = []
            self.cached = False

    def _fake_retrieve(db, *, request, context=None,
                       generation_provider=None):
        return _FakeOutcome()

    monkeypatch.setattr(
        ret_svc, "retrieve_research_context", _fake_retrieve,
    )
    yield


def _mk_user(uids):
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(User(
            id=uid, email=f"m28p-{uid.hex[:8]}@e.com", password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


def _setup_with_manuscript(uid):
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        pid = p.id
    rid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(Report(
            id=rid, user_id=uid, project_id=pid,
            topic="T", output_language="en",
        ))
        db.commit()
    with SessionLocal() as db:
        planner_svc.generate_research_plan(
            db, user_id=uid, project_id=pid
        )
    with SessionLocal() as db:
        result = builder_svc.generate_manuscript(
            db, user_id=uid, report_id=rid
        )
        version_id = result.version.id
    with SessionLocal() as db:
        section = db.execute(
            select(ManuscriptSection).where(
                ManuscriptSection.manuscript_version_id == version_id
            ).order_by(ManuscriptSection.display_order.asc()).limit(1)
        ).scalar_one()
        section_id = section.id
    return pid, rid, version_id, section_id


def test_persist_section_research_completes(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid, rid, vid, sid = _setup_with_manuscript(uid)

    with SessionLocal() as db:
        result = persist_svc.run_section_research_persisted(
            db, user_id=uid, report_id=rid, section_id=sid,
        )
    assert result.skipped is False
    assert result.run.status == "completed"
    assert result.run.context_hash
    assert result.run.contract_hash

    with SessionLocal() as db:
        count = db.execute(
            select(func.count()).select_from(SectionResearchRun).where(
                SectionResearchRun.manuscript_section_id == sid,
            )
        ).scalar_one()
    assert count == 1


def test_persist_section_research_is_idempotent(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid, rid, vid, sid = _setup_with_manuscript(uid)

    with SessionLocal() as db:
        r1 = persist_svc.run_section_research_persisted(
            db, user_id=uid, report_id=rid, section_id=sid,
        )
    assert r1.skipped is False
    assert r1.run.status == "completed"

    with SessionLocal() as db:
        r2 = persist_svc.run_section_research_persisted(
            db, user_id=uid, report_id=rid, section_id=sid,
        )
    assert r2.skipped is True
    assert r2.run.status == "skipped"
    assert r2.run.context_hash == r1.run.context_hash

    with SessionLocal() as db:
        completed = db.execute(
            select(func.count()).select_from(SectionResearchRun).where(
                SectionResearchRun.manuscript_section_id == sid,
                SectionResearchRun.status == "completed",
            )
        ).scalar_one()
        skipped = db.execute(
            select(func.count()).select_from(SectionResearchRun).where(
                SectionResearchRun.manuscript_section_id == sid,
                SectionResearchRun.status == "skipped",
            )
        ).scalar_one()
    assert completed == 1
    assert skipped == 1
