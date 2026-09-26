"""M27 — Manuscript Architect routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.exceptions import (
    ManuscriptNotFound,
    ManuscriptSectionNotFound,
)
from app.db.models.manuscript_draft import ManuscriptDraft
from app.db.models.manuscript import (
    Manuscript,
    ManuscriptSection,
    ManuscriptSectionDependency,
    ManuscriptVersion,
)
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.manuscript import (
    ManuscriptCurrentRead,
    ManuscriptGenerateRequest,
    ManuscriptGenerateResponse,
    ManuscriptDraftRead,
    ManuscriptDraftUpdateRequest,
    ManuscriptRead,
    ManuscriptSectionDependencyRead,
    ManuscriptSectionRead,
    ManuscriptValidationRead,
    ManuscriptVersionListResponse,
    ManuscriptVersionRead,
)
from app.services import reports as reports_service
from app.services.manuscript import builder as builder_svc
from app.services.manuscript import jobs as jobs_svc
from app.services.manuscript import validation as val_svc
from app.services.manuscript.ordering import research_order_for_sections

router = APIRouter(prefix="/reports", tags=["manuscript"])


def _load_sections(
    db: Session, *, version_id: uuid.UUID
) -> list[ManuscriptSection]:
    return list(db.execute(
        select(ManuscriptSection)
        .where(ManuscriptSection.manuscript_version_id == version_id)
        .order_by(ManuscriptSection.display_order.asc())
    ).scalars().all())


def _load_dependencies(
    db: Session, *, version_id: uuid.UUID
) -> list[ManuscriptSectionDependency]:
    return list(db.execute(
        select(ManuscriptSectionDependency)
        .where(
            ManuscriptSectionDependency.manuscript_version_id == version_id
        )
    ).scalars().all())


def _current_manuscript(
    db: Session, *, report_id: uuid.UUID
) -> Manuscript:
    ms = db.execute(
        select(Manuscript).where(Manuscript.report_id == report_id)
    ).scalar_one_or_none()
    if ms is None:
        raise ManuscriptNotFound()
    return ms


@router.post(
    "/{report_id}/manuscript/generate",
    response_model=ManuscriptGenerateResponse,
)
def generate_manuscript(
    report_id: uuid.UUID,
    body: ManuscriptGenerateRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptGenerateResponse:
    reports_service.get_report(
        db, user_id=current_user.id, report_id=report_id
    )
    settings = get_settings()

    effective_async = bool(body.async_)
    if effective_async and not getattr(
        settings, "manuscript_async_jobs", False
    ):
        effective_async = False

    if effective_async:
        job_id = jobs_svc.enqueue_manuscript_generate(
            db,
            report_id=report_id,
            user_id=current_user.id,
            force=body.force,
        )
        response.status_code = 202
        return ManuscriptGenerateResponse(
            status="queued", job_id=job_id
        )

    result = builder_svc.generate_manuscript(
        db,
        user_id=current_user.id,
        report_id=report_id,
        force=body.force,
        commit=True,
    )
    response.status_code = 200
    if result.manuscript is None or result.version is None:
        return ManuscriptGenerateResponse(
            status=result.run.status,
            context_hash=result.run.context_hash,
        )
    sections = _load_sections(db, version_id=result.version.id)
    deps = _load_dependencies(db, version_id=result.version.id)
    return ManuscriptGenerateResponse(
        status=result.run.status,
        manuscript_id=result.manuscript.id,
        version_id=result.version.id,
        context_hash=result.run.context_hash,
        section_count=len(sections),
        research_order=research_order_for_sections(
            sections=sections, dependencies=deps
        ),
    )


@router.get(
    "/{report_id}/manuscript",
    response_model=ManuscriptCurrentRead,
)
def get_current_manuscript(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptCurrentRead:
    reports_service.get_report(
        db, user_id=current_user.id, report_id=report_id
    )
    ms = _current_manuscript(db, report_id=report_id)
    if ms.current_version_id is None:
        raise ManuscriptNotFound()
    version = db.get(ManuscriptVersion, ms.current_version_id)
    if version is None:
        raise ManuscriptNotFound()
    sections = _load_sections(db, version_id=version.id)
    deps = _load_dependencies(db, version_id=version.id)
    return ManuscriptCurrentRead(
        manuscript=ManuscriptRead.model_validate(ms),
        version=ManuscriptVersionRead.model_validate(version),
        sections=[
            ManuscriptSectionRead.model_validate(s) for s in sections
        ],
        dependencies=[
            ManuscriptSectionDependencyRead.model_validate(d)
            for d in deps
        ],
        research_order=research_order_for_sections(
            sections=sections, dependencies=deps
        ),
    )


@router.get(
    "/{report_id}/manuscript/versions",
    response_model=ManuscriptVersionListResponse,
)
def list_versions(
    report_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptVersionListResponse:
    reports_service.get_report(
        db, user_id=current_user.id, report_id=report_id
    )
    ms = _current_manuscript(db, report_id=report_id)
    base = select(ManuscriptVersion).where(
        ManuscriptVersion.manuscript_id == ms.id
    )
    total = int(db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one())
    rows = list(db.execute(
        base.order_by(ManuscriptVersion.version.desc())
        .limit(limit).offset(offset)
    ).scalars().all())
    return ManuscriptVersionListResponse(
        items=[ManuscriptVersionRead.model_validate(r) for r in rows],
        total=total, limit=limit, offset=offset,
    )


@router.post(
    "/{report_id}/manuscript/validate",
    response_model=ManuscriptValidationRead,
)
def validate_manuscript(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptValidationRead:
    reports_service.get_report(
        db, user_id=current_user.id, report_id=report_id
    )
    ms = _current_manuscript(db, report_id=report_id)
    if ms.current_version_id is None:
        raise ManuscriptNotFound()
    version = db.get(ManuscriptVersion, ms.current_version_id)
    if version is None:
        raise ManuscriptNotFound()

    sections = _load_sections(db, version_id=version.id)
    deps = _load_dependencies(db, version_id=version.id)

    settings = get_settings()
    result = val_svc.validate_persisted_manuscript(
        sections=sections,
        dependencies=deps,
        word_target=int(version.word_target or 0),
        budget_tolerance=float(
            getattr(settings, "manuscript_budget_tolerance", 0.10)
        ),
    )
    return ManuscriptValidationRead(**result.as_dict())


@router.get(
    "/{report_id}/manuscript/sections/{section_key}",
    response_model=ManuscriptSectionRead,
)
def get_section(
    report_id: uuid.UUID,
    section_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptSectionRead:
    reports_service.get_report(
        db, user_id=current_user.id, report_id=report_id
    )
    ms = _current_manuscript(db, report_id=report_id)
    if ms.current_version_id is None:
        raise ManuscriptNotFound()
    row = db.execute(
        select(ManuscriptSection).where(
            ManuscriptSection.manuscript_version_id == ms.current_version_id,
            ManuscriptSection.section_key == section_key,
        )
    ).scalar_one_or_none()
    if row is None:
        raise ManuscriptSectionNotFound()
    return ManuscriptSectionRead.model_validate(row)


@router.get(
    "/{report_id}/manuscript/draft",
    response_model=ManuscriptDraftRead,
)
def get_draft(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptDraftRead:
    reports_service.get_report(
        db,
        user_id=current_user.id,
        report_id=report_id,
    )
    manuscript = _load_current_manuscript(
        db,
        report_id=report_id,
    )
    draft = db.execute(
        select(ManuscriptDraft).where(
            ManuscriptDraft.manuscript_id == manuscript.id
        )
    ).scalar_one_or_none()
    if draft is None:
        raise ManuscriptNotFound("No autosaved draft exists.")
    return ManuscriptDraftRead.model_validate(draft)


@router.patch(
    "/{report_id}/manuscript/draft",
    response_model=ManuscriptDraftRead,
)
def autosave_draft(
    report_id: uuid.UUID,
    body: ManuscriptDraftUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ManuscriptDraftRead:
    reports_service.get_report(
        db,
        user_id=current_user.id,
        report_id=report_id,
    )
    manuscript = _load_current_manuscript(
        db,
        report_id=report_id,
    )
    draft = db.execute(
        select(ManuscriptDraft).where(
            ManuscriptDraft.manuscript_id == manuscript.id
        )
    ).scalar_one_or_none()

    digest = hashlib.sha256(
        json.dumps(
            body.sections,
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    if draft is None:
        draft = ManuscriptDraft(
            manuscript_id=manuscript.id,
            updated_by=current_user.id,
            base_version_id=body.base_version_id or manuscript.current_version_id,
            sections=body.sections,
            draft_hash=digest,
        )
        db.add(draft)
    else:
        draft.updated_by = current_user.id
        draft.base_version_id = (
            body.base_version_id
            if body.base_version_id is not None
            else draft.base_version_id
        )
        draft.sections = body.sections
        draft.draft_hash = digest

    db.commit()
    db.refresh(draft)
    return ManuscriptDraftRead.model_validate(draft)
