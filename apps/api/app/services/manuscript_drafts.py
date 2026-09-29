from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.manuscript_exceptions import (
    ManuscriptDraftConflictError,
    ManuscriptDraftNotFound,
)
from app.db.models.manuscript import (
    Manuscript,
    ManuscriptSection,
    ManuscriptSectionDependency,
    ManuscriptVersion,
)
from app.db.models.manuscript_draft import ManuscriptDraft
from app.services.reports import get_report


def get_draft(
    db: Session,
    *,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ManuscriptDraft:
    get_report(db, user_id=user_id, report_id=report_id)
    manuscript = db.execute(
        select(Manuscript).where(Manuscript.report_id == report_id)
    ).scalar_one_or_none()
    if manuscript is None:
        raise ManuscriptDraftNotFound()
    draft = db.execute(
        select(ManuscriptDraft).where(
            ManuscriptDraft.manuscript_id == manuscript.id
        )
    ).scalar_one_or_none()
    if draft is None:
        raise ManuscriptDraftNotFound()
    return draft


def autosave(
    db: Session,
    *,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
    base_version_id: uuid.UUID,
    revision: int,
    content: dict[str, Any],
) -> ManuscriptDraft:
    get_report(db, user_id=user_id, report_id=report_id)
    manuscript = db.execute(
        select(Manuscript).where(Manuscript.report_id == report_id)
    ).scalar_one_or_none()
    if manuscript is None or manuscript.current_version_id is None:
        raise ManuscriptDraftNotFound()

    # Verify the client is writing against the current immutable version.
    if manuscript.current_version_id != base_version_id:
        raise ManuscriptDraftConflictError(
            message="Manuscript changed since this draft was opened."
        )

    draft = db.execute(
        select(ManuscriptDraft)
        .where(ManuscriptDraft.manuscript_id == manuscript.id)
        .with_for_update()
    ).scalar_one_or_none()

    if draft is None:
        if revision != 0:
            raise ManuscriptDraftConflictError(
                message="Draft revision is stale; reload the manuscript."
            )
        draft = ManuscriptDraft(
            report_id=report_id,
            manuscript_id=manuscript.id,
            base_version_id=base_version_id,
            revision=0,
            content=content,
            updated_by=user_id,
        )
        db.add(draft)
        db.flush()
        return draft

    if (
        draft.base_version_id != base_version_id
        or draft.revision != revision
    ):
        raise ManuscriptDraftConflictError(
            message="Draft revision is stale; reload the latest draft.",
        )

    draft.content = content
    draft.revision += 1
    draft.updated_by = user_id
    db.flush()
    return draft


def discard(
    db: Session,
    *,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    draft = get_draft(db, report_id=report_id, user_id=user_id)
    db.delete(draft)
    db.flush()


def commit_draft(
    db: Session,
    *,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
    base_version_id: uuid.UUID,
    revision: int,
) -> ManuscriptVersion:
    """Materialize a draft as a new immutable manuscript version.

    The draft content is stored as JSON and must contain section objects
    compatible with the existing manuscript editor. The new version
    records the prior version as its parent and updates current_version_id
    only after the new version has been persisted.
    """
    get_report(db, user_id=user_id, report_id=report_id)
    manuscript = db.execute(
        select(Manuscript)
        .where(Manuscript.report_id == report_id)
        .with_for_update()
    ).scalar_one_or_none()
    if manuscript is None or manuscript.current_version_id is None:
        raise ManuscriptDraftNotFound()

    draft = db.execute(
        select(ManuscriptDraft)
        .where(ManuscriptDraft.manuscript_id == manuscript.id)
        .with_for_update()
    ).scalar_one_or_none()
    if draft is None:
        raise ManuscriptDraftNotFound()
    if (
        manuscript.current_version_id != base_version_id
        or draft.base_version_id != base_version_id
        or draft.revision != revision
    ):
        raise ManuscriptDraftConflictError(
            message="Manuscript draft is stale; reload before saving.",
        )

    base = db.get(ManuscriptVersion, base_version_id)
    if base is None:
        raise ManuscriptDraftNotFound()

    version_no = int(
        db.execute(
            select(ManuscriptVersion.version)
            .where(ManuscriptVersion.manuscript_id == manuscript.id)
            .order_by(ManuscriptVersion.version.desc())
            .limit(1)
        ).scalar_one()
    ) + 1

    content = draft.content
    title = str(content.get("title") or base.title)
    abstract_direction = content.get("abstract_direction")
    if abstract_direction is not None and not isinstance(abstract_direction, dict):
        raise ManuscriptDraftConflictError(message="Invalid abstract payload.")

    base_sections = list(
        db.execute(
            select(ManuscriptSection)
            .where(ManuscriptSection.manuscript_version_id == base.id)
            .order_by(ManuscriptSection.display_order.asc())
        ).scalars().all()
    )
    raw_sections = content.get("sections")
    if raw_sections is None:
        raw_sections = []
    if not isinstance(raw_sections, list):
        raise ManuscriptDraftConflictError(message="Invalid manuscript sections payload.")

    overrides_by_key: dict[str, dict[str, Any]] = {}
    for item in raw_sections:
        if not isinstance(item, dict):
            raise ManuscriptDraftConflictError(message="Invalid manuscript section payload.")
        key = str(item.get("section_key") or "").strip()
        if not key or key in overrides_by_key:
            raise ManuscriptDraftConflictError(message="Duplicate or missing section key.")
        overrides_by_key[key] = item

    base_keys = {section.section_key for section in base_sections}
    unknown_keys = sorted(set(overrides_by_key) - base_keys)
    if unknown_keys:
        raise ManuscriptDraftConflictError(
            message="Draft contains unknown manuscript sections: " + ", ".join(unknown_keys)
        )

    version = ManuscriptVersion(
        manuscript_id=manuscript.id,
        version=version_no,
        status="draft",
        architecture_version=base.architecture_version,
        template_version=base.template_version,
        research_plan_id=base.research_plan_id,
        research_plan_version=base.research_plan_version,
        research_plan_context_hash=base.research_plan_context_hash,
        context_hash=f"manual-draft:{draft.id}:{draft.revision}",
        title=title,
        title_rationale=base.title_rationale,
        abstract_direction=abstract_direction,
        word_target=int(content.get("word_target") or base.word_target),
        sections_snapshot=content.get("sections"),
        architecture_meta=base.architecture_meta,
        created_by=user_id,
        parent_version_id=base.id,
    )
    db.add(version)
    db.flush()

    section_id_by_key: dict[str, uuid.UUID] = {}
    for base_section in base_sections:
        override = overrides_by_key.get(base_section.section_key, {})
        section = ManuscriptSection(
            manuscript_version_id=version.id,
            source_research_plan_section_id=base_section.source_research_plan_section_id,
            section_key=base_section.section_key,
            title=str(override.get("title") or base_section.title),
            purpose=(
                override["purpose"]
                if "purpose" in override
                else base_section.purpose
            ),
            section_type=base_section.section_type,
            display_order=int(override.get("display_order", base_section.display_order)),
            required=base_section.required,
            word_budget=max(
                0,
                int(override.get("word_budget", base_section.word_budget)),
            ),
            budget_weight=base_section.budget_weight,
            evidence_coverage_target=base_section.evidence_coverage_target,
            research_objective=base_section.research_objective,
            writing_objective=base_section.writing_objective,
            citation_required=base_section.citation_required,
            research_contract=base_section.research_contract,
            section_meta=base_section.section_meta,
            status=str(override.get("status") or base_section.status),
        )
        db.add(section)
        db.flush()
        section_id_by_key[section.section_key] = section.id

    base_dependencies = list(
        db.execute(
            select(ManuscriptSectionDependency)
            .where(ManuscriptSectionDependency.manuscript_version_id == base.id)
        ).scalars().all()
    )
    for dependency in base_dependencies:
        upstream_base = db.get(ManuscriptSection, dependency.upstream_section_id)
        downstream_base = db.get(ManuscriptSection, dependency.downstream_section_id)
        if upstream_base is None or downstream_base is None:
            continue
        upstream_id = section_id_by_key.get(upstream_base.section_key)
        downstream_id = section_id_by_key.get(downstream_base.section_key)
        if upstream_id is None or downstream_id is None:
            continue
        db.add(
            ManuscriptSectionDependency(
                manuscript_version_id=version.id,
                upstream_section_id=upstream_id,
                downstream_section_id=downstream_id,
                dependency_type=dependency.dependency_type,
                dependency_meta=dependency.dependency_meta,
            )
        )

    manuscript.current_version_id = version.id
    db.delete(draft)
    db.flush()
    return version
