"""M23 — Literature intelligence pipeline orchestrator.

Stages run inside a single try/except with ONE commit at the end.
The advisory lock + hash + idempotency check + stages + run record
are all inside that try, so failures at any point are audited.

Concurrency: advisory lock serializes runs for the same project.
Dedup: partial unique index on
(project_id, context_hash, analysis_version) where status='completed'.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.literature import (
    LiteratureIntelligenceRun,
    ProjectLiteratureItem,
)
from app.db.models.project import Project, ProjectEvent
from app.db.models.research_classification import ProjectClassification
from app.domain.literature import (
    LITERATURE_INTELLIGENCE_VERSION,
    RunStatus,
)
from app.services.literature import (
    characterization,
    clustering,
    context,
    corpus,
    gaps,
    screening,
    synthesis,
)

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    run: LiteratureIntelligenceRun
    skipped: bool


def _emit_event(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID | None,
    event_type: str,
    event_meta: dict,
) -> None:
    db.add(
        ProjectEvent(
            project_id=project_id,
            user_id=user_id,
            event_type=event_type,
            event_meta=event_meta,
        )
    )


def _record_run(
    db: Session,
    *,
    project_id: uuid.UUID,
    context_hash: str | None,
    status: str,
    source_count: int = 0,
    included_count: int = 0,
    excluded_count: int = 0,
    cluster_count: int = 0,
    gap_count: int = 0,
    duration_ms: int | None = None,
    error_message: str | None = None,
) -> LiteratureIntelligenceRun:
    run = LiteratureIntelligenceRun(
        project_id=project_id,
        context_hash=context_hash,
        analysis_version=LITERATURE_INTELLIGENCE_VERSION,
        status=status,
        source_count=source_count,
        included_count=included_count,
        excluded_count=excluded_count,
        cluster_count=cluster_count,
        gap_count=gap_count,
        duration_ms=duration_ms,
        error_message=error_message,
    )
    db.add(run)
    return run


def _lock_project(db: Session, *, project_id: uuid.UUID) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": f"lit_intel:{project_id}"},
    )


def _find_completed_run(
    db: Session,
    *,
    project_id: uuid.UUID,
    context_hash: str,
) -> uuid.UUID | None:
    return db.execute(
        select(LiteratureIntelligenceRun.id)
        .where(
            LiteratureIntelligenceRun.project_id == project_id,
            LiteratureIntelligenceRun.context_hash == context_hash,
            LiteratureIntelligenceRun.analysis_version
            == LITERATURE_INTELLIGENCE_VERSION,
            LiteratureIntelligenceRun.status
            == RunStatus.COMPLETED.value,
        )
        .limit(1)
    ).scalar_one_or_none()


def run_literature_analysis(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    project_id: uuid.UUID,
    force: bool = False,
    commit: bool = True,
) -> PipelineResult:
    settings = get_settings()
    if not getattr(settings, "literature_enabled", True):
        raise RuntimeError("literature subsystem disabled")

    started = time.perf_counter()

    project = db.get(Project, project_id)
    if project is None or project.status == "archived":
        raise RuntimeError("project not found or archived")

    context_hash: str | None = None

    try:
        # --- Phase 0: lock + hash --------------------------------
        _lock_project(db, project_id=project_id)
        context_hash = context.build_literature_context_hash(
            db, project_id=project_id
        )

        # --- Phase 1: idempotency ---------------------------------
        if not force:
            existing_id = _find_completed_run(
                db,
                project_id=project_id,
                context_hash=context_hash,
            )
            if existing_id is not None:
                duration_ms = int(
                    (time.perf_counter() - started) * 1000
                )
                _emit_event(
                    db,
                    project_id=project_id,
                    user_id=user_id,
                    event_type="literature_analysis_skipped",
                    event_meta={
                        "context_hash": context_hash,
                        "analysis_version": (
                            LITERATURE_INTELLIGENCE_VERSION
                        ),
                    },
                )
                skipped_run = _record_run(
                    db,
                    project_id=project_id,
                    context_hash=context_hash,
                    status=RunStatus.SKIPPED.value,
                    duration_ms=duration_ms,
                )
                if commit:
                    db.commit()
                return PipelineResult(run=skipped_run, skipped=True)

        _emit_event(
            db,
            project_id=project_id,
            user_id=user_id,
            event_type="literature_analysis_started",
            event_meta={
                "context_hash": context_hash,
                "analysis_version": LITERATURE_INTELLIGENCE_VERSION,
            },
        )
        db.flush()

        # --- Phase 2: stages (no internal commits) ----------------
        corpus.sync_project_literature_corpus(
            db, user_id=user_id, project_id=project_id
        )

        cls = db.execute(
            select(ProjectClassification).where(
                ProjectClassification.project_id == project_id
            )
        ).scalar_one_or_none()

        items = list(
            db.execute(
                select(ProjectLiteratureItem).where(
                    ProjectLiteratureItem.project_id == project_id
                )
            ).scalars().all()
        )
        sources_by_id = corpus.get_sources_for_items(db, items=items)

        for item in items:
            src = sources_by_id.get(item.source_id)
            if src is None:
                item.analysis_status = "failed"
                item.analysis_error = "source_missing"
                continue
            try:
                screening.apply_screening(
                    db,
                    item=item,
                    source=src,
                    classification=cls,
                )
                characterization.apply_characterization(
                    db, item=item, source=src
                )
                item.analysis_status = "completed"
                item.analysis_version = LITERATURE_INTELLIGENCE_VERSION
                item.analysis_error = None
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "literature_item_analysis_failed item_id=%s",
                    item.id,
                )
                item.analysis_status = "failed"
                item.analysis_error = str(exc)[:400]
        db.flush()

        clusters = clustering.cluster_project_literature(
            db, project_id=project_id
        )
        _emit_event(
            db,
            project_id=project_id,
            user_id=user_id,
            event_type="literature_cluster_completed",
            event_meta={
                "context_hash": context_hash,
                "cluster_count": len(clusters),
            },
        )

        synthesis.synthesize_project_clusters(
            db, project_id=project_id
        )

        gap_count = gaps.detect_project_gaps(
            db,
            project_id=project_id,
            sources_by_id=sources_by_id,
        )
        _emit_event(
            db,
            project_id=project_id,
            user_id=user_id,
            event_type="literature_gap_detected",
            event_meta={
                "context_hash": context_hash,
                "gap_count": gap_count,
            },
        )

        # --- Phase 3: counts + completed run ----------------------
        all_items = list(
            db.execute(
                select(ProjectLiteratureItem).where(
                    ProjectLiteratureItem.project_id == project_id
                )
            ).scalars().all()
        )
        included = sum(
            1 for i in all_items
            if i.screening_status in ("candidate", "included")
        )
        excluded = sum(
            1 for i in all_items
            if i.screening_status == "excluded"
        )

        duration_ms = int((time.perf_counter() - started) * 1000)
        run = _record_run(
            db,
            project_id=project_id,
            context_hash=context_hash,
            status=RunStatus.COMPLETED.value,
            source_count=len(all_items),
            included_count=included,
            excluded_count=excluded,
            cluster_count=len(clusters),
            gap_count=gap_count,
            duration_ms=duration_ms,
        )
        _emit_event(
            db,
            project_id=project_id,
            user_id=user_id,
            event_type="literature_analysis_completed",
            event_meta={
                "context_hash": context_hash,
                "analysis_version": LITERATURE_INTELLIGENCE_VERSION,
                "duration_ms": duration_ms,
                "cluster_count": len(clusters),
                "gap_count": gap_count,
            },
        )
        db.flush()

        if commit:
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                logger.info(
                    "literature_run_deduped_by_index project_id=%s",
                    project_id,
                )
                existing_id = _find_completed_run(
                    db,
                    project_id=project_id,
                    context_hash=context_hash or "",
                )
                existing = (
                    db.get(LiteratureIntelligenceRun, existing_id)
                    if existing_id else None
                )
                if existing is None:
                    raise
                return PipelineResult(run=existing, skipped=True)
            db.refresh(run)
        return PipelineResult(run=run, skipped=False)

    except Exception as exc:  # noqa: BLE001
        db.rollback()
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.exception(
            "literature_analysis_failed project_id=%s", project_id
        )
        try:
            fail_run = _record_run(
                db,
                project_id=project_id,
                context_hash=context_hash,
                status=RunStatus.FAILED.value,
                duration_ms=duration_ms,
                error_message=str(exc)[:500],
            )
            _emit_event(
                db,
                project_id=project_id,
                user_id=user_id,
                event_type="literature_analysis_failed",
                event_meta={
                    "context_hash": context_hash,
                    "error": str(exc)[:200],
                    "duration_ms": duration_ms,
                },
            )
            if commit:
                db.commit()
                db.refresh(fail_run)
        except Exception:  # noqa: BLE001
            logger.exception("literature_failure_persist_failed")
            db.rollback()
        raise


__all__ = ["PipelineResult", "run_literature_analysis"]
