"""M24 — Coverage engine tests."""
from __future__ import annotations

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
from app.db.session import SessionLocal
from app.services import projects as projects_service
from app.services.research_planning import coverage


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
        rids = select(Report.id).where(Report.project_id.in_(pids))
        db.execute(delete(Source).where(Source.report_id.in_(rids)))
        db.execute(delete(Report).where(Report.project_id.in_(pids)))
        db.execute(delete(Project).where(Project.user_id.in_(uids)))
        db.execute(delete(User).where(User.id.in_(uids)))
        db.commit()


def _mk_user(uids) -> uuid.UUID:
    uid = uuid.uuid4()
    with SessionLocal() as db:
        db.add(User(
            id=uid, email=f"rp-cov-{uid.hex[:8]}@e.com",
            password_hash="x",
        ))
        db.commit()
    uids.append(uid)
    return uid


class _Req:
    __slots__ = (
        "requirement_key", "min_sources", "preferred_paper_types",
        "preferred_research_designs", "max_age_years",
        "full_text_required", "min_relevance_score", "coverage_weight",
    )

    def __init__(self, key="r1", min_sources=2, **kw):
        self.requirement_key = key
        self.min_sources = min_sources
        self.preferred_paper_types = kw.get("preferred_paper_types")
        self.preferred_research_designs = kw.get(
            "preferred_research_designs"
        )
        self.max_age_years = kw.get("max_age_years")
        self.full_text_required = kw.get("full_text_required", False)
        self.min_relevance_score = kw.get("min_relevance_score")
        self.coverage_weight = kw.get("coverage_weight", 1.0)


def test_full_text_detection_via_extracted_at():
    from types import SimpleNamespace
    ok = SimpleNamespace(extracted_at="2024", status="extracted")
    assert coverage._is_full_text(ok) is True
    bad = SimpleNamespace(extracted_at=None, status="abstract_only")
    assert coverage._is_full_text(bad) is False
    assert coverage._is_full_text(None) is False


def _seed_lit_run_and_items(
    db, *, uid, pid, n_sources, paper_type="systematic_review",
    year=2024, status="abstract_only",
):
    r = Report(
        user_id=uid, project_id=pid, topic="R",
        output_language="en", status="draft",
    )
    db.add(r)
    db.flush()
    for i in range(n_sources):
        s = Source(
            report_id=r.id, title=f"T{i}",
            year=year, status=status,
        )
        db.add(s)
        db.flush()
        db.add(ProjectLiteratureItem(
            project_id=pid,
            source_id=s.id,
            screening_status="included",
            paper_type_code=paper_type,
        ))
    db.add(LiteratureIntelligenceRun(
        project_id=pid,
        context_hash="h",
        analysis_version="m23.1",
        status="completed",
    ))


def test_no_literature_run_returns_zero(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P"
        )
        pid = p.id

    with SessionLocal() as db:
        out = coverage.compute_corpus_coverage(
            db, project_id=pid, requirements=[_Req()]
        )
    assert out["coverage_score"] == 0.0
    assert out["coverage_state"] == "no_literature_run"


def test_high_coverage_with_matching_sources(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P"
        )
        pid = p.id
        _seed_lit_run_and_items(db, uid=uid, pid=pid, n_sources=5)
        db.commit()

    with SessionLocal() as db:
        out = coverage.compute_corpus_coverage(
            db, project_id=pid,
            requirements=[_Req(min_sources=2)],
        )
    assert out["coverage_state"] == "computed"
    assert out["coverage_score"] == 1.0


def test_paper_type_mismatch_lowers_coverage(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P"
        )
        pid = p.id
        _seed_lit_run_and_items(
            db, uid=uid, pid=pid, n_sources=3,
            paper_type="editorial",
        )
        db.commit()

    with SessionLocal() as db:
        out = coverage.compute_corpus_coverage(
            db, project_id=pid,
            requirements=[_Req(
                min_sources=2,
                preferred_paper_types=["systematic_review"],
            )],
        )
    assert out["coverage_score"] == 0.0


def test_recency_filter_lowers_coverage(cleanup_users):
    uid = _mk_user(cleanup_users)
    with SessionLocal() as db:
        p = projects_service.create_project(
            db, user_id=uid, name="P"
        )
        pid = p.id
        _seed_lit_run_and_items(
            db, uid=uid, pid=pid, n_sources=3, year=2000,
        )
        db.commit()

    with SessionLocal() as db:
        out = coverage.compute_corpus_coverage(
            db, project_id=pid,
            requirements=[_Req(min_sources=2, max_age_years=5)],
        )
    assert out["coverage_score"] == 0.0
