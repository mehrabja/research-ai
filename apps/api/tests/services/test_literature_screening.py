"""M23 — Literature screening tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models.literature import ProjectLiteratureItem
from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.db.models.research_classification import ProjectClassification
from app.db.models.research_taxonomy import (
    ResearchDomain as ResearchDomainRow,
)
from app.db.models.source import Source
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.services import projects as projects_service
from app.services.literature import screening


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
                email=f"lit-scr-{uid.hex[:8]}@e.com",
                password_hash="x",
            )
        )
        db.commit()
    uids.append(uid)
    return uid


def _mk_source(
    uid: uuid.UUID,
    *,
    title: str,
    abstract: str | None = None,
    citation_count: int | None = None,
    year: int | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
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

        # Seed a ProjectClassification with the taxonomy domain_id
        # so screening has a real domain to compare against.
        dom = db.execute(
            select(ResearchDomainRow).where(
                ResearchDomainRow.code == "computer_science"
            )
        ).scalar_one_or_none()
        if dom is not None:
            db.add(
                ProjectClassification(
                    project_id=p.id,
                    domain_id=dom.id,
                    status="needs_review",
                    classifier_version="m21.1",
                    taxonomy_version="m21.1",
                )
            )
            db.flush()

        s = Source(
            report_id=r.id,
            title=title,
            abstract=abstract,
            citation_count=citation_count,
            year=year,
            status="abstract_only" if abstract else "metadata_only",
        )
        db.add(s)
        db.commit()
        return p.id, s.id

def test_relevant_source_scores_high(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P", domain="computer_science"
        )
        p.research_questions = ["deep learning methods"]
        dom = db.execute(
            select(ResearchDomainRow).where(
                ResearchDomainRow.code == "computer_science"
            )
        ).scalar_one_or_none()
        db.add(
            ProjectClassification(
                project_id=p.id,
                domain_id=dom.id if dom else None,
                paper_type_code="systematic_review",
                status="needs_review",
                classifier_version="m21.1",
                taxonomy_version="m21.1",
            )
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
        s_rel = Source(
            report_id=r.id,
            title=(
                "A systematic review of deep learning for "
                "computer science"
            ),
            abstract=(
                "A systematic review of deep learning methods "
                "in computing."
            ),
            citation_count=100,
            year=2023,
            status="abstract_only",
        )
        db.add(s_rel)
        db.flush()
        item = ProjectLiteratureItem(
            project_id=p.id, source_id=s_rel.id
        )
        db.add(item)
        db.flush()
        result = screening.screen_literature_item(
            db, item=item, source=s_rel
        )
    assert result.relevance_score >= 0.5
    assert result.screening_status == "candidate"

def test_irrelevant_source_scores_low(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid, sid = _mk_source(uid, title="X")
    with SessionLocal() as db:
        item = ProjectLiteratureItem(project_id=pid, source_id=sid)
        db.add(item)
        db.flush()
        src = db.get(Source, sid)
        result = screening.screen_literature_item(
            db, item=item, source=src
        )
    assert result.relevance_score < 0.5
    assert result.screening_status == "discovered"


def test_missing_metadata_does_not_crash(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid, sid = _mk_source(uid, title="Only title")
    with SessionLocal() as db:
        item = ProjectLiteratureItem(project_id=pid, source_id=sid)
        db.add(item)
        db.flush()
        src = db.get(Source, sid)
        result = screening.screen_literature_item(
            db, item=item, source=src
        )
    assert isinstance(result.relevance_score, float)


def test_screening_reason_is_explainable(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid, sid = _mk_source(
        uid, title="P", abstract="some abstract", year=2020
    )
    with SessionLocal() as db:
        item = ProjectLiteratureItem(project_id=pid, source_id=sid)
        db.add(item)
        db.flush()
        src = db.get(Source, sid)
        result = screening.screen_literature_item(
            db, item=item, source=src
        )
    assert result.reason
    assert isinstance(result.factors, list)
    assert len(result.factors) >= 3
    for f in result.factors:
        assert {"name", "weight", "value"} <= set(f.keys())
