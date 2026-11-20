"""M28.5 — Idempotent persistence with durable failure."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    ManuscriptProseConfigurationInvalid,
    ManuscriptProseInvalid,
)
from app.db.models.manuscript import (
    Manuscript,
    ManuscriptSection,
    ManuscriptVersion,
)
from app.db.models.manuscript_prose import (
    ManuscriptProseParagraph,
    ManuscriptProseRun,
    ManuscriptProseSection,
    ManuscriptProseSentence,
)
from app.db.models.project import Project
from app.db.models.report import Report
from app.db.session import SessionLocal
from app.domain.manuscript_prose import (
    M28_5_VERSION,
    PROSE_PROMPT_VERSION,
    ProseGenerationMode,
    ProseRunStatus,
    ProseSectionStatus,
)
from app.services.manuscript_prose import context as ctx_svc
from app.services.manuscript_prose import evidence as ev_svc
from app.services.manuscript_prose import generator as gen_svc
from app.services.manuscript_prose import validation as val_svc
from app.services.manuscript_prose.contracts import build_section_contract
from app.services.manuscript_prose.serialization import (
    layout_section,
    paragraph_hash,
    sentence_hash,
    word_count,
)

logger = logging.getLogger(__name__)


@dataclass
class PersistedM28_5Result:
    run: ManuscriptProseRun
    skipped: bool


def _lock_report(db: Session, *, report_id: uuid.UUID) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": f"manuscript_prose:{report_id}"},
    )


def _completed_run(
    db: Session,
    *,
    report_id: uuid.UUID,
    base_manuscript_version_id: uuid.UUID,
    context_hash: str,
) -> ManuscriptProseRun | None:
    return db.execute(
        select(ManuscriptProseRun).where(
            ManuscriptProseRun.report_id == report_id,
            ManuscriptProseRun.base_manuscript_version_id
            == base_manuscript_version_id,
            ManuscriptProseRun.context_hash == context_hash,
            ManuscriptProseRun.prose_version == M28_5_VERSION,
            ManuscriptProseRun.status == ProseRunStatus.COMPLETED.value,
        )
    ).scalar_one_or_none()


def _persist_failed_run(
    *,
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    manuscript_id: uuid.UUID | None,
    base_manuscript_version_id: uuid.UUID,
    context_hash: str | None,
    mode: str,
    provider: str | None,
    model: str | None,
    error_message: str,
    duration_ms: int,
) -> None:
    try:
        with SessionLocal() as s:
            now = datetime.now(UTC)
            s.add(ManuscriptProseRun(
                project_id=project_id,
                report_id=report_id,
                manuscript_id=manuscript_id or base_manuscript_version_id,
                base_manuscript_version_id=base_manuscript_version_id,
                context_hash=context_hash or "-",
                prose_version=M28_5_VERSION,
                prompt_version=PROSE_PROMPT_VERSION,
                generation_mode=mode,
                provider=provider,
                model=model,
                status=ProseRunStatus.FAILED.value,
                error_message=error_message[:500],
                duration_ms=int(duration_ms),
                completed_at=now,
            ))
            s.commit()
    except Exception:
        logger.exception("m28_5_failed_run_audit_failed")


def run_m28_5_persisted(
    db: Session,
    *,
    report_id: uuid.UUID,
    base_manuscript_version_id: uuid.UUID,
    mode: str | None = None,
    force: bool = False,
    commit: bool = True,
) -> PersistedM28_5Result:
    settings = get_settings()
    if not settings.manuscript_prose_enabled:
        raise ManuscriptProseConfigurationInvalid(
            "manuscript prose is disabled"
        )

    report = db.get(Report, report_id)
    if report is None or report.project_id is None:
        raise ManuscriptProseInvalid("report has no project")
    project = db.get(Project, report.project_id)
    if project is None:
        raise ManuscriptProseInvalid("project not found")
    version = db.get(ManuscriptVersion, base_manuscript_version_id)
    if version is None:
        raise ManuscriptProseInvalid("manuscript version not found")
    manuscript = db.get(Manuscript, version.manuscript_id)
    if manuscript is None or manuscript.report_id != report_id:
        raise ManuscriptProseInvalid("manuscript mismatch")

    effective_mode = (
        mode or settings.manuscript_prose_default_mode
    )
    provider = settings.manuscript_prose_provider or None
    model = settings.manuscript_prose_model or None

    started = datetime.now(UTC)
    context_hash: str | None = None

    try:
        _lock_report(db, report_id=report_id)

        context_hash = ctx_svc.compute_m28_5_context_hash(
            db,
            manuscript_version_id=base_manuscript_version_id,
            mode=effective_mode,
            provider=provider,
            model=model,
        )

        existing = _completed_run(
            db,
            report_id=report_id,
            base_manuscript_version_id=base_manuscript_version_id,
            context_hash=context_hash,
        )
        if existing is not None:
            return PersistedM28_5Result(run=existing, skipped=True)

        run = ManuscriptProseRun(
            project_id=report.project_id,
            report_id=report_id,
            manuscript_id=manuscript.id,
            base_manuscript_version_id=base_manuscript_version_id,
            research_plan_id=version.research_plan_id,
            context_hash=context_hash,
            prose_version=M28_5_VERSION,
            prompt_version=PROSE_PROMPT_VERSION,
            generation_mode=effective_mode,
            provider=provider,
            model=model,
            status=ProseRunStatus.RUNNING.value,
            started_at=started,
        )
        db.add(run)
        db.flush()

        sections = list(db.execute(
            select(ManuscriptSection)
            .where(
                ManuscriptSection.manuscript_version_id
                == base_manuscript_version_id,
                ManuscriptSection.status == "active",
            )
            .order_by(ManuscriptSection.display_order.asc())
        ).scalars().all())

        max_sections = int(settings.manuscript_prose_max_sections)
        sections = sections[:max_sections]

        total_words = 0
        total_paragraphs = 0
        total_sentences = 0
        section_rows_written = 0
        run_warnings: list[str] = []

        global_sentence_ordinal = 0
        cursor = 0

        for section in sections:
            contract = build_section_contract(section)
            packet = ev_svc.build_evidence_packet(
                db,
                project_id=report.project_id,
                report_id=report_id,
                manuscript_version_id=base_manuscript_version_id,
                section=section,
                max_evidence=int(
                    settings.manuscript_prose_max_evidence_per_section
                ),
                max_technical=int(
                    settings
                    .manuscript_prose_max_technical_facts_per_section
                ),
            )

            generated = gen_svc.generate_section(
                db,
                contract=contract,
                packet=packet,
                mode=effective_mode,
                workspace_id=project.workspace_id,
                user_id=report.user_id,
                project_id=report.project_id,
                report_id=report_id,
            )

            known_ev = {str(x.evidence_id) for x in packet.m28_items}
            known_ev |= {str(x.fact_id) for x in packet.technical_facts}
            known_ev |= {
                str(x.result_id) for x in packet.experiment_results
            }
            known_ev |= {str(x.metric_id) for x in packet.metrics}
            known_cit = {
                str(x.identity_id) for x in packet.citation_candidates
            }

            outcome = val_svc.validate_section(
                generated.unit,
                known_evidence_ids=known_ev,
                known_citation_ids=known_cit,
                max_words=max(
                    int(contract.word_budget or 0) * 2, 500,
                ),
            )

            if outcome.status != "valid":
                run_warnings.extend(outcome.errors[:3])

            layout_section(generated.unit, cursor)
            body = generated.unit.text
            cursor = generated.unit.paragraphs[-1].char_end + 2 \
                if generated.unit.paragraphs else cursor

            section_status = ProseSectionStatus.COMPLETED.value
            if "insufficient_evidence" in (generated.warnings or []):
                section_status = (
                    ProseSectionStatus.INSUFFICIENT_EVIDENCE.value
                )

            sec_row = ManuscriptProseSection(
                run_id=run.id,
                project_id=report.project_id,
                report_id=report_id,
                manuscript_version_id=base_manuscript_version_id,
                manuscript_section_id=section.id,
                section_key=contract.section_key,
                section_type=contract.section_type,
                display_order=contract.display_order,
                title=contract.title,
                status=section_status,
                text=body,
                char_start=0,
                char_end=len(body),
                word_count=word_count(body),
                paragraph_count=generated.unit.paragraph_count,
                sentence_count=generated.unit.sentence_count,
                section_context_hash=context_hash,
                provenance=generated.unit.provenance,
                warnings=generated.unit.warnings or None,
            )
            db.add(sec_row)
            db.flush()

            for p in generated.unit.paragraphs:
                p_row = ManuscriptProseParagraph(
                    section_row_id=sec_row.id,
                    run_id=run.id,
                    project_id=report.project_id,
                    ordinal=p.ordinal,
                    text=p.text,
                    char_start=p.char_start,
                    char_end=p.char_end,
                    sentence_count=len(p.sentences),
                    paragraph_hash=paragraph_hash(p.text),
                    provenance=None,
                )
                db.add(p_row)
                db.flush()
                for s in p.sentences:
                    db.add(ManuscriptProseSentence(
                        paragraph_row_id=p_row.id,
                        section_row_id=sec_row.id,
                        run_id=run.id,
                        project_id=report.project_id,
                        ordinal=s.ordinal if hasattr(s, "ordinal") else 0,
                        global_ordinal=global_sentence_ordinal,
                        text=s.text,
                        char_start=s.char_start,
                        char_end=s.char_end,
                        sentence_hash=sentence_hash(s.text),
                        evidence_refs=s.evidence_refs or None,
                        citation_refs=s.citation_refs or None,
                        provenance=None,
                    ))
                    global_sentence_ordinal += 1
                    total_sentences += 1
                total_paragraphs += 1

            total_words += word_count(body)
            section_rows_written += 1

        now = datetime.now(UTC)
        run.status = ProseRunStatus.COMPLETED.value
        run.section_count = section_rows_written
        run.paragraph_count = total_paragraphs
        run.sentence_count = total_sentences
        run.word_count = total_words
        run.warnings = list(run_warnings) or None
        run.output_summary = {
            "section_count": section_rows_written,
            "paragraph_count": total_paragraphs,
            "sentence_count": total_sentences,
            "word_count": total_words,
        }
        run.duration_ms = int(
            (now - started).total_seconds() * 1000
        )
        run.completed_at = now

        if commit:
            db.commit()
            db.refresh(run)
        else:
            db.flush()
        return PersistedM28_5Result(run=run, skipped=False)

    except Exception as exc:
        logger.exception("manuscript_prose_persist_failed")
        if commit:
            try:
                db.rollback()
            except Exception:
                logger.exception("m28_5_rollback_failed")
        duration_ms = int(
            (datetime.now(UTC) - started).total_seconds() * 1000
        )
        _persist_failed_run(
            project_id=report.project_id,
            report_id=report_id,
            manuscript_id=manuscript.id if manuscript else None,
            base_manuscript_version_id=base_manuscript_version_id,
            context_hash=context_hash,
            mode=effective_mode,
            provider=provider,
            model=model,
            error_message=str(exc),
            duration_ms=duration_ms,
        )
        raise


__all__ = ["PersistedM28_5Result", "run_m28_5_persisted"]


_ = ProseGenerationMode  # documented
