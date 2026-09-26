"""M27 — M28 executable contract test."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

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


def _mk_user(uids):
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(User(
            id=uid, email=f"m28-{uid.hex[:8]}@e.com", password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


def test_contract_has_intent_mapping_and_citation(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        pid = p.id
    rid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(Report(
            id=rid, user_id=uid, project_id=pid,
            topic="X", output_language="en",
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
            select(ManuscriptSection)
            .where(ManuscriptSection.manuscript_version_id == version_id)
            .where(ManuscriptSection.section_key == "introduction")
        ).scalar_one()

    contract = section.research_contract
    assert contract["section_key"] == "introduction"
    assert isinstance(contract["retrieval_intents"], list)
    assert (
        contract["intent_mapping_version"] == "m27-intent-v1"
    )
    assert "evidence_requirements" in contract
    assert "source_constraints" in contract
    assert contract["citation_required"] is True

    known = {
        "background", "definition", "methodology", "empirical_evidence",
        "comparison", "causal_evidence", "recent_evidence",
        "counter_evidence", "limitation", "gap", "synthesis", "citation",
    }
    for intent in contract["retrieval_intents"]:
        assert intent in known
    for req in contract["evidence_requirements"]:
        for intent in req["retrieval_intents"]:
            assert intent in known
