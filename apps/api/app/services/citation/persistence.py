"""M30 — Idempotent persistence with durable failure audit."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    CitationConfigurationInvalid,
    CitationInvalid,
)
from app.db.models.citation import (
    CitationIdentity,
    CitationRun,
    Claim,
    ClaimCitation,
    ClaimEvidence,
)
from app.db.models.manuscript import Manuscript, ManuscriptVersion
from app.db.models.report import Report
from app.db.models.source import Source
from app.db.session import SessionLocal
from app.domain.citation import (
    M30_VERSION,
    CitationRunStatus,
    CitationStyle,
    ClaimStatus,
    is_supporting,
)
from app.services.citation import context as ctx_svc
from app.services.citation import coverage as cov_svc
from app.services.citation import engine as engine_svc
from app.services.citation.identity import resolve_identity

logger = logging.getLogger(__name__)


@dataclass
class PersistedCitationResult:
    run: CitationRun
    skipped: bool


def _lock_report(db: Session, *, report_id: uuid.UUID) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": f"citation:{report_id}"},
    )


def _completed_run(
    db: Session,
    *,
    report_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    context_hash: str,
    citation_style: str,
) -> CitationRun | None:
    return db.execute(
        select(CitationRun).where(
            CitationRun.report_id == report_id,
            CitationRun.manuscript_version_id == manuscript_version_id,
            CitationRun.context_hash == context_hash,
            CitationRun.m30_version == M30_VERSION,
            CitationRun.citation_style == citation_style,
            CitationRun.status == CitationRunStatus.COMPLETED.value,
        )
    ).scalar_one_or_none()


def _persist_failed_run(
    *,
    report_id: uuid.UUID,
    manuscript_id: uuid.UUID | None,
    manuscript_version_id: uuid.UUID,
    context_hash: str | None,
    citation_style: str,
    error_message: str,
    duration_ms: int,
) -> None:
    try:
        with SessionLocal() as s:
            now = datetime.now(UTC)
            s.add(CitationRun(
                report_id=report_id,
                manuscript_id=manuscript_id,
                manuscript_version_id=manuscript_version_id,
                context_hash=context_hash or "-",
                m30_version=M30_VERSION,
                citation_style=citation_style,
                status=CitationRunStatus.FAILED.value,
                error_message=error_message[:500],
                duration_ms=int(duration_ms),
                completed_at=now,
            ))
            s.commit()
    except Exception:
        logger.exception("m30_failed_run_audit_failed")


def _build_first_seen(
    *, ordered_citations: list[ClaimCitation],
) -> dict[str, int]:
    """Citation first-appearance order in manuscript prose.

    Ordering key = (paragraph_index, sentence_index, char_start).
    Lower tuple = earlier appearance.
    """
    seen: dict[str, tuple[int, int, int]] = {}
    for cc in ordered_citations:
        cid = str(cc.citation_id)
        key = (
            cc.paragraph_index if cc.paragraph_index is not None else 10**6,
            cc.sentence_index if cc.sentence_index is not None else 10**6,
            cc.char_start if cc.char_start is not None else 10**6,
        )
        if cid not in seen or key < seen[cid]:
            seen[cid] = key
    sorted_ids = sorted(seen.items(), key=lambda kv: (kv[1], kv[0]))
    return {cid: idx + 1 for idx, (cid, _) in enumerate(sorted_ids)}


def run_citation_persisted(
    db: Session,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    manuscript_version_id: uuid.UUID,
    citation_style: str = CitationStyle.AUTHOR_YEAR.value,
    force: bool = False,
    commit: bool = True,
) -> PersistedCitationResult:
    settings = get_settings()
    if not settings.citation_enabled:
        raise CitationConfigurationInvalid("citation is disabled")

    if citation_style not in (
        CitationStyle.NUMERIC.value, CitationStyle.AUTHOR_YEAR.value,
    ):
        raise CitationInvalid("unknown citation style")

    report = db.get(Report, report_id)
    if report is None or report.project_id is None:
        raise CitationInvalid("report has no project")
    version = db.get(ManuscriptVersion, manuscript_version_id)
    if version is None:
        raise CitationInvalid("manuscript version not found")
    manuscript = db.get(Manuscript, version.manuscript_id)
    if manuscript is None or manuscript.report_id != report_id:
        raise CitationInvalid("manuscript mismatch")

    started = datetime.now(UTC)
    context_hash: str | None = None

    try:
        _lock_report(db, report_id=report_id)

        context_hash = ctx_svc.compute_m30_context_hash(
            db,
            manuscript_version_id=manuscript_version_id,
            citation_style=citation_style,
        )

        existing = _completed_run(
            db,
            report_id=report_id,
            manuscript_version_id=manuscript_version_id,
            context_hash=context_hash,
            citation_style=citation_style,
        )
        if existing is not None:
            now = datetime.now(UTC)
            skipped = CitationRun(
                report_id=report_id,
                manuscript_id=manuscript.id,
                manuscript_version_id=manuscript_version_id,
                context_hash=context_hash,
                m30_version=M30_VERSION,
                citation_style=citation_style,
                status=CitationRunStatus.SKIPPED.value,
                claim_count=existing.claim_count,
                citation_count=existing.citation_count,
                unsupported_count=existing.unsupported_count,
                mixed_support_count=existing.mixed_support_count,
                duplicate_reference_count=(
                    existing.duplicate_reference_count
                ),
                coverage_score=existing.coverage_score,
                warnings=["reused_previous_completed_run"],
                duration_ms=0,
                completed_at=now,
            )
            db.add(skipped)
            if commit:
                db.commit()
                db.refresh(skipped)
            else:
                db.flush()
            return PersistedCitationResult(run=skipped, skipped=True)

        run = CitationRun(
            report_id=report_id,
            manuscript_id=manuscript.id,
            manuscript_version_id=manuscript_version_id,
            context_hash=context_hash,
            m30_version=M30_VERSION,
            citation_style=citation_style,
            status=CitationRunStatus.RUNNING.value,
            claim_count=0,
            citation_count=0,
            unsupported_count=0,
            mixed_support_count=0,
            duplicate_reference_count=0,
            coverage_score=Decimal("0"),
        )
        db.add(run)
        db.flush()

        result = engine_svc.run_citation_engine(
            db,
            report_id=report_id,
            manuscript_version_id=manuscript_version_id,
            project_id=report.project_id,
            citation_style=citation_style,
            context_hash=context_hash,
        )

        # --- prose unavailable: finish immediately with warning ---
        if not result.prose_available:
            now = datetime.now(UTC)
            run.status = CitationRunStatus.COMPLETED.value
            run.claim_count = 0
            run.citation_count = 0
            run.unsupported_count = 0
            run.mixed_support_count = 0
            run.duplicate_reference_count = 0
            run.coverage_score = Decimal("0")
            run.input_snapshot = {
                "report_id": str(report_id),
                "manuscript_version_id": str(manuscript_version_id),
                "citation_style": citation_style,
                "prose_available": False,
            }
            run.output_summary = {
                "prose_available": False,
                "claim_count": 0,
                "citation_count": 0,
            }
            run.warnings = list(result.warnings)
            run.duration_ms = int(result.duration_ms)
            run.completed_at = now
            if commit:
                db.commit()
                db.refresh(run)
            else:
                db.flush()
            return PersistedCitationResult(run=run, skipped=False)

        # --- full pipeline: prose available ---
        # 1) Persist claims
        claim_rows: dict[str, Claim] = {}
        for ec in result.claims:
            c = Claim(
                citation_run_id=run.id,
                manuscript_version_id=manuscript_version_id,
                manuscript_section_id=ec.manuscript_section_id,
                claim_hash=ec.claim_hash,
                claim_text=ec.claim_text,
                claim_type=ec.claim_type,
                location=ec.location,
                claim_meta=None,
                status=ClaimStatus.EXTRACTED.value,
            )
            db.add(c)
            db.flush()
            claim_rows[ec.claim_hash] = c

        # 2) Resolve identity per real source in report
        sources = list(db.execute(
            select(Source).where(Source.report_id == report_id)
        ).scalars().all())
        identity_by_source: dict[uuid.UUID, CitationIdentity] = {}
        for s in sources:
            r = resolve_identity(db, report_id=report_id, source=s)
            identity_by_source[s.id] = r.identity

        # 3) Persist evidence, ClaimCitation, compute first-seen
        supported_with_source = 0
        supported_without_source = 0
        partially_supported = 0
        unsupported = 0
        contradicted = 0
        used_identities: set[uuid.UUID] = set()
        all_claim_citations: list[ClaimCitation] = []

        for ec in result.claims:
            c = claim_rows[ec.claim_hash]
            mapped = result.mappings.get(ec.claim_hash, [])
            best_level = None
            best_source_id: uuid.UUID | None = None
            for m in mapped:
                db.add(ClaimEvidence(
                    claim_id=c.id,
                    evidence_type=m.evidence_type,
                    evidence_id=m.evidence_id,
                    source_id=m.source_id,
                    support_level=m.support_level,
                    relevance_score=Decimal(str(m.relevance_score)),
                    provenance=m.provenance,
                ))
                if m.support_level == "supports":
                    best_level = "supports"
                elif (
                    m.support_level == "partially_supports"
                    and best_level != "supports"
                ):
                    best_level = "partially_supports"
                elif (
                    m.support_level == "contradicts"
                    and best_level is None
                ):
                    best_level = "contradicts"

                if (
                    m.source_id is not None
                    and m.source_id in identity_by_source
                ):
                    ident = identity_by_source[m.source_id]
                    used_identities.add(ident.id)
                    cc = ClaimCitation(
                        claim_id=c.id,
                        citation_id=ident.id,
                        relation_type=m.support_level,
                        support_level=m.support_level,
                        relevance_score=Decimal(
                            str(m.relevance_score)
                        ),
                        paragraph_index=None,
                        sentence_index=(
                            (ec.location or {}).get("sentence_index")
                            if ec.location else None
                        ),
                        char_start=(
                            (ec.location or {}).get("char_start")
                            if ec.location else None
                        ),
                        char_end=(
                            (ec.location or {}).get("char_end")
                            if ec.location else None
                        ),
                        citation_order=None,
                    )
                    db.add(cc)
                    all_claim_citations.append(cc)
                    if best_source_id is None:
                        best_source_id = ident.source_id

            if best_level == "supports":
                if best_source_id is not None:
                    supported_with_source += 1
                else:
                    supported_without_source += 1
                c.status = ClaimStatus.MAPPED.value
            elif best_level == "partially_supports":
                partially_supported += 1
                c.status = ClaimStatus.MAPPED.value
            elif best_level == "contradicts":
                contradicted += 1
                c.status = ClaimStatus.MAPPED.value
            else:
                unsupported += 1
                c.status = ClaimStatus.UNSUPPORTED.value

        db.flush()

        # 4) Assign numeric citation_order by first appearance
        first_seen = _build_first_seen(
            ordered_citations=all_claim_citations,
        )
        for cc in all_claim_citations:
            cc.citation_order = first_seen.get(str(cc.citation_id))

        # 5) Duplicate reference count
        by_key: dict[str, int] = {}
        for ident in identity_by_source.values():
            by_key[ident.identity_key] = by_key.get(
                ident.identity_key, 0,
            ) + 1
        dup_count = sum(max(0, n - 1) for n in by_key.values())

        # 6) Coverage
        coverage = cov_svc.compute_coverage(
            claim_count=len(result.claims),
            supported_with_source_count=supported_with_source,
            supported_without_source_count=supported_without_source,
            partially_supported_claim_count=partially_supported,
            unsupported_claim_count=unsupported,
            contradicted_claim_count=contradicted,
            citation_count=len(used_identities),
            duplicate_reference_count=dup_count,
        )

        now = datetime.now(UTC)
        run.status = CitationRunStatus.COMPLETED.value
        run.claim_count = coverage.claim_count
        run.citation_count = coverage.citation_count
        run.unsupported_count = coverage.unsupported_claim_count
        run.mixed_support_count = (
            coverage.partially_supported_claim_count
        )
        run.duplicate_reference_count = (
            coverage.duplicate_reference_count
        )
        run.coverage_score = Decimal(str(coverage.coverage_score))
        run.input_snapshot = {
            "report_id": str(report_id),
            "manuscript_version_id": str(manuscript_version_id),
            "citation_style": citation_style,
            "prose_available": True,
        }
        run.output_summary = {
            "prose_available": True,
            "supported_with_source": supported_with_source,
            "supported_without_source": supported_without_source,
            "partially_supported": partially_supported,
            "unsupported": unsupported,
            "contradicted": contradicted,
            "citation_count": coverage.citation_count,
            "coverage_score": coverage.coverage_score,
            "citation_density": coverage.citation_density,
        }
        run.warnings = list(result.warnings)
        run.duration_ms = int(result.duration_ms)
        run.completed_at = now

        _ = is_supporting  # reserved
        if commit:
            db.commit()
            db.refresh(run)
        else:
            db.flush()
        return PersistedCitationResult(run=run, skipped=False)

    except Exception as exc:
        logger.exception("citation_persist_failed")
        if commit:
            try:
                db.rollback()
            except Exception:
                logger.exception("m30_rollback_failed")
        duration_ms = int(
            (datetime.now(UTC) - started).total_seconds() * 1000
        )
        _persist_failed_run(
            report_id=report_id,
            manuscript_id=manuscript.id if manuscript else None,
            manuscript_version_id=manuscript_version_id,
            context_hash=context_hash,
            citation_style=citation_style,
            error_message=str(exc),
            duration_ms=duration_ms,
        )
        raise


__all__ = ["PersistedCitationResult", "run_citation_persisted"]
