"""M33 — Publication target profile CRUD + versioning."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import (
    PublicationTargetConflict,
    PublicationTargetInvalid,
    PublicationTargetNotFound,
)
from app.db.models.publication import (
    PublicationTarget,
    PublicationTargetSelection,
)
from app.db.models.report import Report
from app.domain.publication import (
    CITATION_STYLES,
    PUBLICATION_PROFILE_SCHEMA_VERSION,
    TARGET_VENUE_TYPES,
)

logger = logging.getLogger(__name__)


def create_target_profile(
    db: Session,
    *,
    target_code: str,
    profile_version: str,
    venue: str,
    venue_type: str,
    citation_style: str,
    publisher: str | None = None,
    paper_types: list | None = None,
    formatting_rules: dict | None = None,
    section_rules: dict | None = None,
    word_limits: dict | None = None,
    abstract_limits: dict | None = None,
    keyword_rules: dict | None = None,
    author_rules: dict | None = None,
    anonymity_rules: dict | None = None,
    figure_table_rules: dict | None = None,
    supplementary_rules: dict | None = None,
    reference_rules: dict | None = None,
    submission_checklist: list | None = None,
    provenance: dict | None = None,
) -> PublicationTarget:
    if not target_code:
        raise PublicationTargetInvalid("target_code is required")
    if not profile_version:
        raise PublicationTargetInvalid("profile_version is required")
    if venue_type not in TARGET_VENUE_TYPES:
        raise PublicationTargetInvalid(
            f"unknown venue_type: {venue_type}"
        )
    if citation_style not in CITATION_STYLES:
        raise PublicationTargetInvalid(
            f"unknown citation_style: {citation_style}"
        )

    existing = db.execute(
        select(PublicationTarget).where(
            PublicationTarget.target_code == target_code,
            PublicationTarget.profile_version == profile_version,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise PublicationTargetConflict(
            "target_code/profile_version already exists"
        )

    target = PublicationTarget(
        target_code=target_code,
        profile_version=profile_version,
        publisher=publisher,
        venue=venue,
        venue_type=venue_type,
        citation_style=citation_style,
        active=True,
        paper_types=paper_types,
        formatting_rules=formatting_rules,
        section_rules=section_rules,
        word_limits=word_limits,
        abstract_limits=abstract_limits,
        keyword_rules=keyword_rules,
        author_rules=author_rules,
        anonymity_rules=anonymity_rules,
        figure_table_rules=figure_table_rules,
        supplementary_rules=supplementary_rules,
        reference_rules=reference_rules,
        submission_checklist=submission_checklist,
        profile_schema_version=PUBLICATION_PROFILE_SCHEMA_VERSION,
        provenance=provenance,
    )
    db.add(target)
    db.flush()
    return target


def list_targets(
    db: Session,
    *,
    target_code: str | None = None,
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[PublicationTarget], int]:
    from sqlalchemy import func

    base = select(PublicationTarget)
    if target_code:
        base = base.where(PublicationTarget.target_code == target_code)
    if active_only:
        base = base.where(PublicationTarget.active.is_(True))
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(
            PublicationTarget.target_code.asc(),
            PublicationTarget.profile_version.desc(),
            PublicationTarget.id.asc(),
        ).limit(limit).offset(offset)
    ).scalars().all())
    return rows, total


def get_target(
    db: Session, *, target_id: uuid.UUID,
) -> PublicationTarget:
    target = db.get(PublicationTarget, target_id)
    if target is None:
        raise PublicationTargetNotFound()
    return target


def get_active_target_by_code(
    db: Session, *, target_code: str,
) -> PublicationTarget:
    target = db.execute(
        select(PublicationTarget)
        .where(
            PublicationTarget.target_code == target_code,
            PublicationTarget.active.is_(True),
        )
        .order_by(
            PublicationTarget.profile_version.desc(),
            PublicationTarget.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    if target is None:
        raise PublicationTargetNotFound()
    return target


def select_target_for_report(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    target_id: uuid.UUID,
    selection_note: str | None = None,
) -> PublicationTargetSelection:
    report = db.get(Report, report_id)
    if report is None or report.user_id != user_id:
        # Preserve repository 404 semantics for foreign reports.
        raise PublicationTargetNotFound()
    target = db.get(PublicationTarget, target_id)
    if target is None or not target.active:
        raise PublicationTargetNotFound()

    # Append-only selection: keep history.
    selection = PublicationTargetSelection(
        report_id=report_id,
        target_id=target_id,
        selected_by=user_id,
        selection_note=selection_note,
    )
    db.add(selection)
    db.flush()
    return selection


def get_current_selection(
    db: Session, *, report_id: uuid.UUID,
) -> PublicationTargetSelection | None:
    return db.execute(
        select(PublicationTargetSelection)
        .where(PublicationTargetSelection.report_id == report_id)
        .order_by(
            PublicationTargetSelection.created_at.desc(),
            PublicationTargetSelection.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()


__all__ = [
    "create_target_profile",
    "list_targets",
    "get_target",
    "get_active_target_by_code",
    "select_target_for_report",
    "get_current_selection",
]
