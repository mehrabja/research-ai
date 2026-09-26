"""M31 — persisted run is idempotent."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.db.models.academic_qa import AcademicQARun
from app.db.models.manuscript import (
    Manuscript,
    ManuscriptSection,
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
from app.services.academic_qa import persistence as qa_persist
from app.services.manuscript import builder as builder_svc
from app.services.research_planning import planner as planner_svc


@pytest.fixture()
def cleanup_users() -> Iterator[list[uuid.UUID]]:
    uids: list[uuid.UUID] = []
    yield uids
    if not uids:
        return
    with SessionLocal() as db:
        pids = [
            r[0] for r in db.execute(
                select(Project.id).where(Project.user_id.in_(uids))
            ).all()
        ]
        rids = [
            r[0] for r in db.execute(
                select(Report.id).where(Report.user_id.in_(uids))
            ).all()
        ]
        plan_ids = [
            r[0] for r in db.execute(
                select(ResearchPlan.id).where(
                    ResearchPlan.project_id.in_(pids)
                )
            ).all()
        ]
        version_ids = [
            r[0] for r in db.execute(
                select(ManuscriptVersion.id).where(
                    ManuscriptVersion.manuscript_id.in_(
                        select(Manuscript.id).where(
                            Manuscript.report_id.in_(rids)
                        )
                    )
                )
            ).all()
        ]
        if rids:
            db.execute(delete(AcademicQARun).where(
                AcademicQARun.report_id.in_(rids)
            ))
        if version_ids:
            db.execute(delete(ManuscriptSection).where(
                ManuscriptSection.manuscript_version_id.in_(version_ids)
            ))
            db.execute(delete(ManuscriptVersion).where(
                ManuscriptVersion.id.in_(version_ids)
            ))
        if rids:
            db.execute(delete(Manuscript).where(
                Manuscript.report_id.in_(rids)
            ))
        if pids:
            db.execute(delete(ResearchPlanRun).where(
                ResearchPlanRun.project_id.in_(pids)
            ))
        if plan_ids:
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
                ResearchPlan.id.in_(plan_ids)
            ))
        if pids:
            db.execute(delete(ProjectEvent).where(
                ProjectEvent.project_id.in_(pids)
            ))
            db.execute(delete(Project).where(Project.id.in_(pids)))
        if rids:
            db.execute(delete(ReportEvent).where(
                ReportEvent.report_id.in_(rids)
            ))
            db.execute(delete(Report).where(Report.id.in_(rids)))
        # M37: purge owned workspaces before deleting user
        db.execute(
            delete(Workspace).where(
                Workspace.owner_user_id.in_(uids)
            )
        )
        db.execute(delete(User).where(User.id.in_(uids)))
        db.commit()


def _mk_user(uids):
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(User(
            id=uid,
            email=f"m31-{uid.hex[:8]}@e.com",
            password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


def _setup(uid):
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science",
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
            db, user_id=uid, project_id=pid,
        )
    with SessionLocal() as db:
        result = builder_svc.generate_manuscript(
            db, user_id=uid, report_id=rid,
        )
        vid = result.version.id
    return rid, vid


def test_persist_idempotent(cleanup_users) -> None:
    uid = _mk_user(cleanup_users)
    rid, vid = _setup(uid)

    with SessionLocal() as db:
        r1 = qa_persist.run_m31_persisted(
            db, report_id=rid, manuscript_version_id=vid, commit=True,
        )
    assert r1.run.status == "completed"
    assert r1.run.gate in ("pass", "pass_with_warnings", "blocked")

    with SessionLocal() as db:
        r2 = qa_persist.run_m31_persisted(
            db, report_id=rid, manuscript_version_id=vid, commit=True,
        )
    assert r2.skipped is True
    assert r2.run.context_hash == r1.run.context_hash
