"""M28.5 — Deterministic + provider-assisted prose generation.

The generator NEVER invents content. Deterministic mode produces
sentence-level skeletons grounded in real evidence. Provider-assisted
mode calls the existing provider abstraction; if unavailable, mode
falls back to deterministic with an explicit warning.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.domain.manuscript_prose import (
    ProseGenerationMode,
)
from app.services.manuscript_prose.contracts import SectionContract
from app.services.manuscript_prose.evidence import EvidencePacket
from app.services.manuscript_prose.serialization import (
    ParagraphUnit,
    SectionUnit,
    SentenceUnit,
    join_sentences,
)

logger = logging.getLogger(__name__)


@dataclass
class GeneratedSection:
    unit: SectionUnit
    mode_used: str
    warnings: list[str] = field(default_factory=list)
    error_message: str | None = None


def _make_paragraph(
    ordinal: int, sentences: list[SentenceUnit],
) -> ParagraphUnit | None:
    if not sentences:
        return None
    p = ParagraphUnit(
        ordinal=ordinal, text="", char_start=0, char_end=0,
        sentences=sentences,
    )
    p.text = join_sentences([s.text for s in sentences])
    return p


def _no_evidence_paragraph(
    contract: SectionContract,
) -> ParagraphUnit:
    no_ev_sentences = [
        SentenceUnit(
            text=(
                f"This section ({contract.section_key}) is marked "
                "as insufficient-evidence: no supported M28/M29 "
                "evidence is currently available for the required "
                "topics."
            ),
            char_start=0,
            char_end=0,
        )
    ]
    p = ParagraphUnit(
        ordinal=0, text="", char_start=0, char_end=0,
        sentences=no_ev_sentences,
    )
    p.text = join_sentences([s.text for s in no_ev_sentences])
    return p


def _deterministic_generate(
    *,
    contract: SectionContract,
    packet: EvidencePacket,
) -> tuple[list[ParagraphUnit], list[str]]:
    warnings: list[str] = []
    paragraphs: list[ParagraphUnit] = []
    ordinal = 0

    if not packet.has_any_evidence:
        warnings.append("insufficient_evidence")
        paragraphs.append(_no_evidence_paragraph(contract))
        return paragraphs, warnings

    # --- paragraph 1: research objective statement ---
    objective = contract.research_objective or contract.purpose
    if objective:
        obj_sentences = [
            SentenceUnit(
                text=(
                    "This section addresses the research objective: "
                    f"{objective}"
                ),
                char_start=0, char_end=0,
            )
        ]
        p = _make_paragraph(ordinal, obj_sentences)
        if p is not None:
            paragraphs.append(p)
            ordinal += 1

    # --- paragraph 2: M28 evidence statements ---
    if packet.m28_items:
        ev_sentences: list[SentenceUnit] = []
        for e in packet.m28_items:
            excerpt = (e.excerpt or "").strip()
            if not excerpt:
                continue
            ev_sentences.append(SentenceUnit(
                text=(
                    f"Available evidence (role={e.evidence_role}) "
                    f"states: {excerpt}"
                ),
                char_start=0, char_end=0,
                evidence_refs=[str(e.evidence_id)],
            ))
        p = _make_paragraph(ordinal, ev_sentences)
        if p is not None:
            paragraphs.append(p)
            ordinal += 1

    # --- paragraph 3: M29 technical facts ---
    if packet.technical_facts:
        fact_sentences: list[SentenceUnit] = []
        for f in packet.technical_facts:
            v = f.fact_value or f.normalized_value or ""
            fact_sentences.append(SentenceUnit(
                text=(
                    "The project's technical analysis records "
                    f"{f.fact_type} '{f.fact_key}'"
                    + (f" = {v!r}" if v else "")
                    + "."
                ),
                char_start=0, char_end=0,
                evidence_refs=[str(f.fact_id)],
            ))
        p = _make_paragraph(ordinal, fact_sentences)
        if p is not None:
            paragraphs.append(p)
            ordinal += 1

    # --- paragraph 4: M29 metrics ---
    if packet.metrics:
        metric_sentences: list[SentenceUnit] = []
        for m in packet.metrics:
            val = (
                m.value_numeric
                if m.value_numeric is not None else m.value_text
            )
            if val is None:
                continue
            tail = ""
            if m.unit:
                tail += f" {m.unit}"
            if m.split:
                tail += f" (split: {m.split})"
            metric_sentences.append(SentenceUnit(
                text=(
                    f"The reported {m.name} metric is {val}{tail}."
                ),
                char_start=0, char_end=0,
                evidence_refs=[str(m.metric_id)],
            ))
        p = _make_paragraph(ordinal, metric_sentences)
        if p is not None:
            paragraphs.append(p)
            ordinal += 1

    # --- paragraph 5: M29 experiment results ---
    if packet.experiment_results:
        res_sentences: list[SentenceUnit] = []
        for r in packet.experiment_results:
            key = (
                f" (key={r.experiment_key})" if r.experiment_key else ""
            )
            res_sentences.append(SentenceUnit(
                text=(
                    f"The {r.result_type} '{r.name}'{key} was "
                    "recorded by the technical analysis pipeline."
                ),
                char_start=0, char_end=0,
                evidence_refs=[str(r.result_id)],
            ))
        p = _make_paragraph(ordinal, res_sentences)
        if p is not None:
            paragraphs.append(p)
            ordinal += 1

    return paragraphs, warnings


def generate_section(
    db: Session,
    *,
    contract: SectionContract,
    packet: EvidencePacket,
    mode: str,
) -> GeneratedSection:
    """Dispatch generation for a single section.

    Provider-assisted mode is not wired in this milestone. The
    deterministic path is the only one that yields prose. Provider
    availability is a deployment concern that must not degrade the
    manuscript's evidence-grounding.
    """
    warnings: list[str] = []
    mode_used = mode

    if mode not in (
        ProseGenerationMode.DETERMINISTIC.value,
        ProseGenerationMode.HYBRID.value,
        ProseGenerationMode.PROVIDER_ASSISTED.value,
    ):
        mode = ProseGenerationMode.DETERMINISTIC.value
        mode_used = mode
        warnings.append(f"unknown_mode_fallback:{mode_used}")

    if mode in (
        ProseGenerationMode.PROVIDER_ASSISTED.value,
        ProseGenerationMode.HYBRID.value,
    ):
        warnings.append(
            f"provider_not_configured:{mode}; used deterministic"
        )
        mode_used = ProseGenerationMode.DETERMINISTIC.value

    paragraphs, dwarn = _deterministic_generate(
        contract=contract, packet=packet,
    )
    warnings.extend(dwarn)

    unit = SectionUnit(
        section_key=contract.section_key,
        section_type=contract.section_type,
        display_order=contract.display_order,
        title=contract.title,
        paragraphs=paragraphs,
        provenance={
            "mode_used": mode_used,
            "m28_evidence_count": len(packet.m28_items),
            "technical_fact_count": len(packet.technical_facts),
            "experiment_result_count": len(packet.experiment_results),
            "metric_count": len(packet.metrics),
            "citation_candidate_count": len(packet.citation_candidates),
        },
        warnings=list(warnings),
    )
    return GeneratedSection(
        unit=unit, mode_used=mode_used, warnings=warnings,
    )


__all__ = ["GeneratedSection", "generate_section"]
