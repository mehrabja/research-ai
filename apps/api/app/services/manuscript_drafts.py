"""Version-safe manuscript draft and save-version service."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ManuscriptDraftConflictError, ManuscriptNotFound
from app.db.models.manuscript import (
    Manuscript,
    ManuscriptSection,
    ManuscriptSectionDependency,
    ManuscriptVersion,
)
from app.db.models.manuscript_draft import ManuscriptDraft, ManuscriptDraftHistory
from app.services.reports import get_report


class ManuscriptDraftConflict(ManuscriptDraftConflictError):
    """Optimistic-lock conflict that exposes the authoritative draft."""

    def __init__(self, message: str, draft: ManuscriptDraft) -> None:
        self.draft = draft
        super().__init__(message)


def _current_manuscript(
    db: Session,
    *,
    report_id: uuid.UUID,
) -> Manuscript:
    ms = db.execute(
        select(Manuscript).where(Manuscript.report_id == report_id)
    ).scalar_one_or_none()
    if ms is None or ms.current_version_id is None:
        raise ManuscriptNotFound()
    return ms


def get_or_create_draft(
    db: Session,
    *,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ManuscriptDraft:
    ms = _current_manuscript(db, report_id=report_id)
    draft = db.execute(
        select(ManuscriptDraft)
        .where(ManuscriptDraft.report_id == report_id)
        .with_for_update()
    ).scalar_one_or_none()
    if draft is None:
        draft = ManuscriptDraft(
            report_id=report_id,
            manuscript_id=ms.id,
            base_version_id=ms.current_version_id,
            revision=0,
            content={},
            updated_by=user_id,
        )
        db.add(draft)
        db.flush()
    return draft


def read_draft(
    db: Session,
    *,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ManuscriptDraft:
    get_report(db, user_id=user_id, report_id=report_id)
    return get_or_create_draft(db, report_id=report_id, user_id=user_id)


def autosave(
    db: Session,
    *,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
    revision: int,
    content: dict[str, Any],
    base_version_id: uuid.UUID | None,
) -> ManuscriptDraft:
    get_report(db, user_id=user_id, report_id=report_id)
    draft = get_or_create_draft(db, report_id=report_id, user_id=user_id)
    if revision != draft.revision:
        raise ManuscriptDraftConflict(
            f"draft revision conflict: expected {revision}, current {draft.revision}",
            draft,
        )
    if base_version_id is not None and draft.base_version_id != base_version_id:
        raise ManuscriptDraftConflict("draft base version changed", draft)

    draft.revision += 1
    draft.content = content
    draft.updated_by = user_id
    if base_version_id is not None:
        draft.base_version_id = base_version_id
    db.add(
        ManuscriptDraftHistory(
            draft_id=draft.id,
            revision=draft.revision,
            content=content,
            saved_by=user_id,
        )
    )
    db.commit()
    db.refresh(draft)
    return draft


def save_version(
    db: Session,
    *,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
    expected_revision: int,
) -> ManuscriptVersion:
    get_report(db, user_id=user_id, report_id=report_id)
    ms = _current_manuscript(db, report_id=report_id)
    draft = get_or_create_draft(db, report_id=report_id, user_id=user_id)
    if draft.revision != expected_revision:
        raise ManuscriptDraftConflict(
            f"draft revision conflict: expected {expected_revision}, current {draft.revision}",
            draft,
        )

    current = db.get(ManuscriptVersion, ms.current_version_id)
    if current is None:
        raise ManuscriptNotFound()

    next_version = int(
        db.execute(
            select(func.max(ManuscriptVersion.version)).where(
                ManuscriptVersion.manuscript_id == ms.id
            )
        ).scalar_one() or 0
    ) + 1

    new_version = ManuscriptVersion(
        manuscript_id=ms.id,
        version=next_version,
        status="draft",
        architecture_version=current.architecture_version,
        template_version=current.template_version,
        research_plan_id=current.research_plan_id,
        research_plan_version=current.research_plan_version,
        research_plan_context_hash=current.research_plan_context_hash,
        context_hash=current.context_hash,
        title=current.title,
        title_rationale=current.title_rationale,
        abstract_direction=current.abstract_direction,
        word_target=current.word_target,
        sections_snapshot=current.sections_snapshot,
        architecture_meta=current.architecture_meta,
        created_by=user_id,
        parent_version_id=current.id,
        content_snapshot=draft.content,
    )
    db.add(new_version)
    db.flush()

    sections = list(
        db.execute(
            select(ManuscriptSection).where(
                ManuscriptSection.manuscript_version_id == current.id
            )
        ).scalars().all()
    )
    section_map: dict[uuid.UUID, ManuscriptSection] = {}
    for section in sections:
        new_section = ManuscriptSection(
            manuscript_version_id=new_version.id,
            source_research_plan_section_id=section.source_research_plan_section_id,
            section_key=section.section_key,
            title=section.title,
            purpose=section.purpose,
            section_type=section.section_type,
            display_order=section.display_order,
            required=section.required,
            word_budget=section.word_budget,
            budget_weight=section.budget_weight,
            evidence_coverage_target=section.evidence_coverage_target,
            research_objective=section.research_objective,
            writing_objective=section.writing_objective,
            citation_required=section.citation_required,
            research_contract=section.research_contract,
            section_meta=section.section_meta,
            status=section.status,
        )
        db.add(new_section)
        db.flush()
        section_map[section.id] = new_section

    deps = list(
        db.execute(
            select(ManuscriptSectionDependency).where(
                ManuscriptSectionDependency.manuscript_version_id == current.id
            )
        ).scalars().all()
    )
    for dep in deps:
        upstream = section_map.get(dep.upstream_section_id)
        downstream = section_map.get(dep.downstream_section_id)
        if upstream is not None and downstream is not None:
            db.add(
                ManuscriptSectionDependency(
                    manuscript_version_id=new_version.id,
                    upstream_section_id=upstream.id,
                    downstream_section_id=downstream.id,
                    dependency_type=dep.dependency_type,
                    dependency_meta=dep.dependency_meta,
                )
            )

    ms.current_version_id = new_version.id
    db.commit()
    db.refresh(new_version)

    draft.base_version_id = new_version.id
    db.commit()
    return new_version
