"""M23 — Literature characterization tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models.literature import ProjectLiteratureItem
from app.db.models.project import Project, ProjectEvent
from app.db.models.report import Report
from app.db.models.source import Source
from app.db.models.user import User
from app.db.models.workspace import Workspace
from app.db.session import SessionLocal
from app.services import projects as projects_service
from app.services.literature import characterization


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
                email=f"lit-ch-{uid.hex[:8]}@e.com",
                password_hash="x",
            )
        )
        db.commit()
    uids.append(uid)
    return uid


def _mk(uid, *, abstract: str, title: str = "T") -> tuple:
    with SessionLocal() as db:
        p = projects_service.create_project(db, user_id=uid, name="P")
        r = Report(
            user_id=uid,
            project_id=p.id,
            topic="R",
            output_language="en",
            status="draft",
        )
        db.add(r)
        db.flush()
        s = Source(
            report_id=r.id,
            title=title,
            abstract=abstract,
            status="abstract_only",
        )
        db.add(s)
        db.commit()
        return p.id, s.id

def test_extracts_paper_type(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid, sid = _mk(
        uid,
        abstract=(
            "This is a systematic review of methods. "
            "We searched multiple databases."
        ),
    )
    with SessionLocal() as db:
        item = ProjectLiteratureItem(project_id=pid, source_id=sid)
        db.add(item)
        db.flush()
        src = db.get(Source, sid)
        result = characterization.characterize_literature_item(
            db, item=item, source=src
        )
    assert result.paper_type_code == "systematic_review"


def test_extracts_design(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid, sid = _mk(
        uid,
        abstract="A randomized controlled trial of 100 patients.",
    )
    with SessionLocal() as db:
        item = ProjectLiteratureItem(project_id=pid, source_id=sid)
        db.add(item)
        db.flush()
        src = db.get(Source, sid)
        result = characterization.characterize_literature_item(
            db, item=item, source=src
        )
    assert result.research_design_code == "randomized_controlled_trial"


def test_missing_fields_remain_none(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid, sid = _mk(uid, abstract="Nothing to extract here.")
    with SessionLocal() as db:
        item = ProjectLiteratureItem(project_id=pid, source_id=sid)
        db.add(item)
        db.flush()
        src = db.get(Source, sid)
        result = characterization.characterize_literature_item(
            db, item=item, source=src
        )
    assert result.sample_size is None
    assert result.population is None


def test_provenance_preserved(cleanup_users):
    uid = _mk_user(cleanup_users)
    pid, sid = _mk(
        uid, abstract="A cohort study of n = 240 participants."
    )
    with SessionLocal() as db:
        item = ProjectLiteratureItem(project_id=pid, source_id=sid)
        db.add(item)
        db.flush()
        src = db.get(Source, sid)
        result = characterization.characterize_literature_item(
            db, item=item, source=src
        )
    if result.sample_size is not None:
        assert any(
            p["field"] == "sample_size" for p in result.provenance
        )
        for p in result.provenance:
            assert "source" in p
            assert "location" in p
            assert "confidence" in p


def test_rerun_clears_stale_derived_fields(cleanup_users):
    """A new extraction that yields no value clears the old value."""
    uid = _mk_user(cleanup_users)
    pid, sid = _mk(
        uid,
        abstract="A qualitative study with no numeric sample size.",
    )
    with SessionLocal() as db:
        item = ProjectLiteratureItem(
            project_id=pid,
            source_id=sid,
            sample_size=999,
            findings_summary="old summary",
            themes=["old-theme"],
            keywords=["old-kw"],
            population="old population",
        )
        db.add(item)
        db.flush()
        src = db.get(Source, sid)
        characterization.apply_characterization(
            db, item=item, source=src
        )
        db.commit()
        assert item.sample_size is None
        assert item.findings_summary is None
        # themes/keywords may be re-extracted from the new abstract;
        # the invariant is that OLD values are gone, not that the
        # new extraction produces nothing.
        if item.themes is not None:
            assert "old-theme" not in item.themes
        if item.keywords is not None:
            assert "old-kw" not in item.keywords
