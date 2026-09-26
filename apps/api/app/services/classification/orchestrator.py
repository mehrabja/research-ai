"""M21/M22 — Classification orchestrator.

Flow:
  1. Build context (pure reads)
  2. Compute context_hash
  3. Lock row, skip-if-unchanged, classify, write result
  4. Persist immutable ClassificationRun (M22)
  5. On failure: savepoint rollback + guarded `failed` state write + run
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    ClassificationInvalidPayload,
    ClassificationNotFound,
)
from app.db.models.project import Project, ProjectEvent
from app.db.models.research_classification import (
    ClassificationEvidence,
    ClassificationRun,
    ProjectClassification,
)
from app.services.classification.context import (
    ClassificationContext,
    build_context,
    compute_context_hash,
)
from app.services.classification.domain_classifier import classify_domain
from app.services.classification.evidence import EvidenceCollector
from app.services.classification.explanation import (
    build_classification_explanation,
)
from app.services.classification.paper_type_classifier import (
    classify_paper_type,
)
from app.services.classification.research_design_classifier import (
    classify_research_design,
)
from app.services.classification.taxonomy import (
    get_domain_by_code,
    get_paper_type,
    get_research_design,
)
from app.services.projects import get_project

logger = logging.getLogger(__name__)


def _emit_project_event(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID | None,
    event_type: str,
    event_meta: dict[str, Any],
) -> None:
    db.add(
        ProjectEvent(
            project_id=project_id,
            user_id=user_id,
            event_type=event_type,
            event_meta=event_meta,
        )
    )


def _create_run(
    db: Session,
    *,
    project_id: uuid.UUID,
    classification_id: uuid.UUID | None,
    context_hash: str | None,
    classifier_version: str,
    taxonomy_version: str,
    status: str,
    domain_code: str | None,
    paper_type_code: str | None,
    research_design_code: str | None,
    confidence_summary: dict[str, Any] | None,
    explanation: dict[str, Any] | None,
    error_message: str | None,
    duration_ms: int | None,
) -> ClassificationRun:
    """Append a run row. Never updated after creation."""
    run = ClassificationRun(
        project_id=project_id,
        classification_id=classification_id,
        context_hash=context_hash,
        classifier_version=classifier_version,
        taxonomy_version=taxonomy_version,
        status=status,
        domain_code=domain_code,
        paper_type_code=paper_type_code,
        research_design_code=research_design_code,
        confidence_summary=confidence_summary,
        explanation=explanation,
        error_message=error_message,
        duration_ms=duration_ms,
    )
    db.add(run)
    return run


def _replace_evidence(
    db: Session,
    *,
    classification_id: uuid.UUID,
    collector: EvidenceCollector,
) -> None:
    db.execute(
        delete(ClassificationEvidence).where(
            ClassificationEvidence.classification_id == classification_id
        )
    )
    for ev in collector.items():
        db.add(
            ClassificationEvidence(
                classification_id=classification_id,
                target=ev.target,
                signal_type=ev.signal_type,
                source_location=ev.source_location,
                matched_text=ev.matched_text,
                weight=ev.weight,
                target_code=ev.target_code,
            )
        )


def _lock_or_create(
    db: Session, *, project_id: uuid.UUID
) -> ProjectClassification:
    settings = get_settings()
    existing = db.execute(
        select(ProjectClassification)
        .where(ProjectClassification.project_id == project_id)
        .with_for_update()
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    # Race-safe insert: if another worker already inserted, do nothing.
    # Then re-select with FOR UPDATE to get whichever row won.
    stmt = (
        pg_insert(ProjectClassification)
        .values(
            project_id=project_id,
            status="pending",
            classifier_version=settings.classification_classifier_version,
            taxonomy_version=settings.classification_taxonomy_version,
        )
        .on_conflict_do_nothing(index_elements=["project_id"])
    )
    db.execute(stmt)
    db.flush()

    return db.execute(
        select(ProjectClassification)
        .where(ProjectClassification.project_id == project_id)
        .with_for_update()
    ).scalar_one()


def get_or_create_classification(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> ProjectClassification:
    existing = db.execute(
        select(ProjectClassification).where(
            ProjectClassification.project_id == project_id
        )
    ).scalar_one_or_none()

    if existing is not None and existing.status in (
        "completed", "needs_review"
    ):
        return existing

    return classify_project(db, project_id=project_id, user_id=user_id)


def _determine_needs_review(
    *,
    domain_conf: float | None,
    domain_missing: bool,
    paper_is_unknown: bool,
    design_is_unknown: bool,
    paper_conf: float | None,
    design_conf: float | None,
    domain_alt: list[dict],
    paper_alt: list[dict],
    design_alt: list[dict],
    threshold: float,
    margin: float,
) -> bool:
    if domain_missing or paper_is_unknown or design_is_unknown:
        return True
    for conf, alts in (
        (domain_conf, domain_alt),
        (paper_conf, paper_alt),
        (design_conf, design_alt),
    ):
        if conf is None:
            return True
        if conf < threshold:
            return True
        if alts:
            second = alts[0].get("confidence", 0.0)
            if (conf - second) < margin:
                return True
    return False


def _write_result(
    db: Session,
    *,
    row: ProjectClassification,
    ctx: ClassificationContext,
    domain_result,
    paper_result,
    design_result,
    context_hash: str,
    needs_review: bool,
    status: str,
) -> None:
    """Update the current-state row. The audit trail lives in
    ClassificationRun, so no events are emitted here."""
    settings = get_settings()
    db.execute(
        delete(ClassificationEvidence).where(
            ClassificationEvidence.classification_id == row.id
        )
    )

    domain_obj = None
    if domain_result.primary_code:
        domain_obj = get_domain_by_code(
            db, code=domain_result.primary_code
        )
    row.domain_id = domain_obj.id if domain_obj else None
    row.domain_source = domain_result.source if domain_obj else None
    row.domain_method = domain_result.method if domain_obj else None
    row.domain_confidence = (
        domain_result.primary_confidence if domain_obj else None
    )
    row.domain_reason = domain_result.reason if domain_obj else None
    row.domain_alternatives = (
        domain_result.alternatives if domain_obj else None
    )

    pt_code = paper_result.primary_code or "unknown"
    if get_paper_type(db, code=pt_code) is None:
        pt_code = "unknown" if get_paper_type(db, code="unknown") else None
    row.paper_type_code = pt_code
    row.paper_type_source = paper_result.source if pt_code else None
    row.paper_type_method = paper_result.method if pt_code else None
    row.paper_type_confidence = (
        paper_result.primary_confidence if pt_code else None
    )
    row.paper_type_reason = paper_result.reason if pt_code else None
    row.paper_type_alternatives = (
        paper_result.alternatives if pt_code else None
    )
    row.paper_type_secondary = paper_result.secondary if pt_code else None

    rd_code = design_result.primary_code or "unknown"
    if get_research_design(db, code=rd_code) is None:
        rd_code = (
            "unknown" if get_research_design(db, code="unknown") else None
        )
    row.research_design_code = rd_code
    row.research_design_source = (
        design_result.source if rd_code else None
    )
    row.research_design_method = (
        design_result.method if rd_code else None
    )
    row.research_design_confidence = (
        design_result.primary_confidence if rd_code else None
    )
    row.research_design_reason = (
        design_result.reason if rd_code else None
    )
    row.research_design_alternatives = (
        design_result.alternatives if rd_code else None
    )

    row.status = status
    row.needs_review = needs_review
    row.error_message = None
    row.classifier_version = settings.classification_classifier_version
    row.taxonomy_version = settings.classification_taxonomy_version
    row.context_hash = context_hash
    row.context_meta = {
        "chunks_used": len(ctx.chunks),
        "has_explicit_domain": bool(ctx.explicit_domain),
    }


def _write_failure(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID | None,
    error: Exception,
    context_hash: str | None,
    duration_ms: int,
) -> None:
    """Record a failed classification attempt.

    * Always creates an immutable ``ClassificationRun(status='failed')``
      so every attempt is auditable.
    * Only transitions the current-state row to ``failed`` when it is
      still ``pending`` — a concurrent success (``completed`` /
      ``needs_review``) is never clobbered.
    """
    settings = get_settings()
    try:
        row = db.execute(
            select(ProjectClassification)
            .where(ProjectClassification.project_id == project_id)
            .with_for_update()
        ).scalar_one_or_none()

        # Ensure a current-state row exists so the run can link to it.
        if row is None:
            row = ProjectClassification(
                project_id=project_id,
                status="pending",
                classifier_version=(
                    settings.classification_classifier_version
                ),
                taxonomy_version=settings.classification_taxonomy_version,
            )
            db.add(row)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                row = db.execute(
                    select(ProjectClassification)
                    .where(
                        ProjectClassification.project_id == project_id
                    )
                    .with_for_update()
                ).scalar_one()

        # Always record the failed attempt.
        _create_run(
            db,
            project_id=project_id,
            classification_id=row.id,
            context_hash=context_hash,
            classifier_version=settings.classification_classifier_version,
            taxonomy_version=settings.classification_taxonomy_version,
            status="failed",
            domain_code=None,
            paper_type_code=None,
            research_design_code=None,
            confidence_summary=None,
            explanation=None,
            error_message=str(error)[:500],
            duration_ms=duration_ms,
        )

        # Only transition the current-state row if it is still pending.
        if row.status == "pending":
            row.status = "failed"
            row.error_message = str(error)[:500]

        _emit_project_event(
            db,
            project_id=project_id,
            user_id=user_id,
            event_type="classification_failed",
            event_meta={
                "error": str(error)[:200],
                "context_hash": context_hash,
                "duration_ms": duration_ms,
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "classification_failure_persist_failed project_id=%s",
            project_id,
        )

def classify_project(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID | None,
    commit: bool = True,
) -> ProjectClassification:
    settings = get_settings()

    if settings.classification_use_llm:
        raise ClassificationInvalidPayload(
            "LLM classification not implemented in M21; "
            "set classification_use_llm=False"
        )

    project = db.get(Project, project_id)
    if project is None:
        raise ClassificationNotFound("project not found")

    started_at = time.perf_counter()

    # Phase 1: context + hash
    try:
        ctx = build_context(db, project=project)
        context_hash = compute_context_hash(ctx)
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        db.rollback()
        _write_failure(
            db,
            project_id=project_id,
            user_id=user_id,
            error=exc,
            context_hash=None,
            duration_ms=duration_ms,
        )
        if commit:
            db.commit()
        raise

    _emit_project_event(
        db,
        project_id=project_id,
        user_id=user_id,
        event_type="classification_started",
        event_meta={
            "context_hash": context_hash,
            "classifier_version": settings.classification_classifier_version,
        },
    )

    # Phase 2: locked write
    savepoint = db.begin_nested()
    try:
        row = _lock_or_create(db, project_id=project_id)

        # Skip-if-unchanged: same context + version → record a
        # ``skipped`` run so the audit trail shows the check happened.
        if (
            row.context_hash == context_hash
            and row.status in ("completed", "needs_review")
            and row.classifier_version
            == settings.classification_classifier_version
            and row.taxonomy_version
            == settings.classification_taxonomy_version
        ):
            duration_ms = int(
                (time.perf_counter() - started_at) * 1000
            )
            _create_run(
                db,
                project_id=project_id,
                classification_id=row.id,
                context_hash=context_hash,
                classifier_version=row.classifier_version,
                taxonomy_version=row.taxonomy_version,
                status="skipped",
                domain_code=None,
                paper_type_code=None,
                research_design_code=None,
                confidence_summary=None,
                explanation=None,
                error_message=None,
                duration_ms=duration_ms,
            )
            _emit_project_event(
                db,
                project_id=project_id,
                user_id=user_id,
                event_type="classification_skipped",
                event_meta={
                    "context_hash": context_hash,
                    "classifier_version": row.classifier_version,
                    "duration_ms": duration_ms,
                },
            )
            savepoint.commit()
            if commit:
                db.commit()
            return row

        collector = EvidenceCollector()
        domain_result = classify_domain(db, ctx=ctx, collector=collector)
        paper_result = classify_paper_type(ctx, collector)
        design_result = classify_research_design(
            ctx,
            paper_type_code=paper_result.primary_code,
            collector=collector,
        )

        needs_review = _determine_needs_review(
            domain_conf=domain_result.primary_confidence,
            domain_missing=(domain_result.primary_code is None),
            paper_is_unknown=(
                paper_result.primary_code in (None, "unknown")
            ),
            design_is_unknown=(
                design_result.primary_code in (None, "unknown")
            ),
            paper_conf=paper_result.primary_confidence,
            design_conf=design_result.primary_confidence,
            domain_alt=domain_result.alternatives,
            paper_alt=paper_result.alternatives,
            design_alt=design_result.alternatives,
            threshold=settings.classification_confidence_threshold,
            margin=settings.classification_review_margin,
        )
        status = "needs_review" if needs_review else "completed"

        _write_result(
            db,
            row=row,
            ctx=ctx,
            domain_result=domain_result,
            paper_result=paper_result,
            design_result=design_result,
            context_hash=context_hash,
            needs_review=needs_review,
            status=status,
        )
        _replace_evidence(
            db, classification_id=row.id, collector=collector
        )

        explanation = build_classification_explanation(
            collector=collector,
            domain_code=domain_result.primary_code,
            paper_type_code=paper_result.primary_code,
            research_design_code=design_result.primary_code,
        )

        duration_ms = int((time.perf_counter() - started_at) * 1000)

        _create_run(
            db,
            project_id=project_id,
            classification_id=row.id,
            context_hash=context_hash,
            classifier_version=settings.classification_classifier_version,
            taxonomy_version=settings.classification_taxonomy_version,
            status=status,
            domain_code=domain_result.primary_code,
            paper_type_code=paper_result.primary_code,
            research_design_code=design_result.primary_code,
            confidence_summary={
                "domain": domain_result.primary_confidence,
                "paper_type": paper_result.primary_confidence,
                "research_design": design_result.primary_confidence,
            },
            explanation=explanation,
            error_message=None,
            duration_ms=duration_ms,
        )

        _emit_project_event(
            db,
            project_id=project_id,
            user_id=user_id,
            event_type="classification_completed",
            event_meta={
                "status": status,
                "context_hash": context_hash,
                "classifier_version": (
                    settings.classification_classifier_version
                ),
                "duration_ms": duration_ms,
            },
        )

        savepoint.commit()
        if commit:
            db.commit()
            db.refresh(row)
        else:
            db.flush()
        return row

    except Exception as exc:  # noqa: BLE001
        if savepoint.is_active:
            savepoint.rollback()
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        logger.exception(
            "classification_failed project_id=%s", project_id
        )
        _write_failure(
            db,
            project_id=project_id,
            user_id=user_id,
            error=exc,
            context_hash=context_hash,
            duration_ms=duration_ms,
        )
        if commit:
            db.commit()
        raise


def recompute_project(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> ProjectClassification:
    get_project(db, user_id=user_id, project_id=project_id)
    return classify_project(
        db, project_id=project_id, user_id=user_id
    )


def override_classification(
    db: Session,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    updates: dict[str, Any],
) -> ProjectClassification:
    from app.services.classification.taxonomy import (
        require_domain,
        require_paper_type,
        require_research_design,
    )

    get_project(db, user_id=user_id, project_id=project_id)
    row = _lock_or_create(db, project_id=project_id)

    if not updates:
        raise ClassificationInvalidPayload("no fields to override")

    touched: list[str] = []

    if "domain_code" in updates:
        code = updates["domain_code"]
        if code is None:
            row.domain_id = None
            row.domain_source = None
            row.domain_method = None
            row.domain_confidence = None
            row.domain_reason = None
            row.domain_alternatives = None
        else:
            dom = require_domain(db, code=str(code))
            row.domain_id = dom.id
            row.domain_source = "user_override"
            row.domain_method = "explicit"
            row.domain_confidence = 1.0
            row.domain_reason = "user override"
            row.domain_alternatives = None
        touched.append("domain")

    if "paper_type_code" in updates:
        code = updates["paper_type_code"]
        if code is None:
            row.paper_type_code = None
            row.paper_type_source = None
            row.paper_type_method = None
            row.paper_type_confidence = None
            row.paper_type_reason = None
            row.paper_type_alternatives = None
            row.paper_type_secondary = None
        else:
            require_paper_type(db, code=str(code))
            row.paper_type_code = str(code)
            row.paper_type_source = "user_override"
            row.paper_type_method = "explicit"
            row.paper_type_confidence = 1.0
            row.paper_type_reason = "user override"
            row.paper_type_alternatives = None
        touched.append("paper_type")

    if "research_design_code" in updates:
        code = updates["research_design_code"]
        if code is None:
            row.research_design_code = None
            row.research_design_source = None
            row.research_design_method = None
            row.research_design_confidence = None
            row.research_design_reason = None
            row.research_design_alternatives = None
        else:
            require_research_design(db, code=str(code))
            row.research_design_code = str(code)
            row.research_design_source = "user_override"
            row.research_design_method = "explicit"
            row.research_design_confidence = 1.0
            row.research_design_reason = "user override"
            row.research_design_alternatives = None
        touched.append("research_design")

    if not touched:
        raise ClassificationInvalidPayload(
            "no known fields to override"
        )

    if (
        row.domain_id is not None
        and row.paper_type_code is not None
        and row.research_design_code is not None
    ):
        row.needs_review = False
        row.status = "completed"
    else:
        row.status = "needs_review"

    row.context_hash = None

    _emit_project_event(
        db,
        project_id=project_id,
        user_id=user_id,
        event_type="classification_overridden",
        event_meta={"fields": sorted(touched)},
    )

    db.commit()
    db.refresh(row)
    return row


def enqueue_recompute_if_enabled(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID | None,
) -> None:
    """Best-effort enqueue. Never raises."""
    settings = get_settings()
    if not settings.classification_enabled:
        return
    try:
        project = db.get(Project, project_id)
        if project is None or project.status == "archived":
            return
        ctx = build_context(db, project=project)
        chash = compute_context_hash(ctx)
        from app.services import jobs as jobs_service
        jobs_service.enqueue_job(
            db,
            job_type="research_classification",
            payload={
                "project_id": str(project_id),
                "context_hash": chash,
            },
            idempotency_key=(
                f"research_classification:{project_id}:{chash}"
            ),
            user_id=user_id,
            max_attempts=settings.classification_job_max_attempts,
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "classification enqueue failed for project_id=%s", project_id
        )
