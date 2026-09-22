"""M24 — End-to-end pipeline test."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.exceptions import ResearchPlanGenerationFailed
from app.db.models.project import Project, ProjectEvent
from app.db.models.research_plan import (
    ResearchEvidenceRequirement,
    ResearchPlan,
    ResearchPlanDependency,
    ResearchPlanSection,
)
from app.db.models.user import User
from app.db.session import SessionLocal
from app.services import projects as projects_service
from app.services.research_planning import planner


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
            delete(ProjectEvent).where(ProjectEvent.project_id.in_(pids))
        )
        db.execute(delete(Project).where(Project.user_id.in_(uids)))
        db.execute(delete(User).where(User.id.in_(uids)))
        db.commit()


def _mk_user(uids) -> uuid.UUID:
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(User(
            id=uid, email=f"rp-pl-{uid.hex[:8]}@e.com",
            password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


def test_full_pipeline_deterministic(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        pid = p.id

    with SessionLocal() as db:
        result = planner.generate_research_plan(
            db, user_id=uid, project_id=pid
        )

    assert result.skipped is False
    assert result.run.status == "completed"
    assert result.plan is not None
    assert result.plan.version == 1
    assert result.plan.status == "ready"

    with SessionLocal() as db:
        plan = db.get(ResearchPlan, result.plan.id)
        sections = list(
            db.execute(
                select(ResearchPlanSection)
                .where(ResearchPlanSection.plan_id == plan.id)
                .order_by(ResearchPlanSection.display_order.asc())
            ).scalars().all()
        )
        reqs = list(
            db.execute(
                select(ResearchEvidenceRequirement).where(
                    ResearchEvidenceRequirement.plan_id == plan.id
                )
            ).scalars().all()
        )
        deps = list(
            db.execute(
                select(ResearchPlanDependency).where(
                    ResearchPlanDependency.plan_id == plan.id
                )
            ).scalars().all()
        )

    assert len(sections) > 0
    keys = [s.section_key for s in sections]
    assert len(keys) == len(set(keys))
    orders = [s.display_order for s in sections]
    assert sorted(orders) == list(range(len(orders)))
    assert len(reqs) > 0
    assert plan.completeness_score is not None
    assert float(plan.completeness_score) > 0.5
    assert plan.coverage_score is not None
    assert 0.0 <= float(plan.coverage_score) <= 1.0
    assert plan.validation_status == "valid"
    assert len(deps) == max(0, len(sections) - 1)


def test_no_classification_falls_back_to_generic(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P"
        )
        pid = p.id

    with SessionLocal() as db:
        result = planner.generate_research_plan(
            db, user_id=uid, project_id=pid
        )
    assert result.plan is not None
    assert result.plan.paper_type_code is None

    with SessionLocal() as db:
        sections = list(
            db.execute(
                select(ResearchPlanSection)
                .where(ResearchPlanSection.plan_id == result.plan.id)
            ).scalars().all()
        )
    keys = {s.section_key for s in sections}
    assert "introduction" in keys
    assert "methods" in keys


def test_archived_project_rejected(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P"
        )
        p.status = "archived"
        db.commit()
        pid = p.id

    with SessionLocal() as db, pytest.raises(
        ResearchPlanGenerationFailed
    ):
        planner.generate_research_plan(
            db, user_id=uid, project_id=pid
        )
