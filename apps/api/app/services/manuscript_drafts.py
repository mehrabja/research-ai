from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.manuscript_exceptions import (
    ManuscriptDraftConflictError,
    ManuscriptDraftNotFound,
)
from app.db.models.manuscript import Manuscript, ManuscriptVersion
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
    manuscript.current_version_id = version.id
    db.delete(draft)
    db.flush()
    return version
