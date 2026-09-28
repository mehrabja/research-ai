"""M28.5 — Deterministic + provider-assisted prose generation.

The generator NEVER invents content. Deterministic mode produces
sentence-level skeletons grounded in real evidence. Provider-assisted
mode calls the existing provider abstraction; if unavailable, mode
falls back to deterministic with an explicit warning.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.generation import GenerationProfile
from app.domain.manuscript_prose import ProseGenerationMode
from app.integrations.generation.base import (
    GenerationProvider,
    GenerationProviderError,
)
from app.providers.registry import (
    ProviderCapability,
    ProviderContext,
    ProviderResolutionError,
    resolve_provider,
)
from app.services.manuscript_prose.contracts import SectionContract
from app.services.manuscript_prose.evidence import EvidencePacket
from app.services.manuscript_prose.prompts import SYSTEM_CONTRACT, build_prompt
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
    provider_name: str | None = None
    model_name: str | None = None


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


def _build_provider() -> tuple[GenerationProvider, GenerationProfile]:
    settings = get_settings()
    profile = GenerationProfile(
        provider=settings.manuscript_prose_provider,
        model=settings.manuscript_prose_model,
        temperature=settings.manuscript_prose_temperature,
        max_output_tokens=settings.manuscript_prose_max_output_tokens,
        profile_version="m28.5-provider-v1",
    )
    provider = resolve_provider(
        capability=ProviderCapability.GENERATION,
        preferred=profile.provider,
        context=ProviderContext(profile=profile),
    )
    return provider, profile


def _parse_provider_output(
    *,
    raw_text: str,
    contract: SectionContract,
) -> list[ParagraphUnit]:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        payload = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("provider returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("provider JSON root must be an object")

    section_id = payload.get("section_id")
    if section_id not in (None, contract.section_key):
        raise ValueError("provider returned mismatched section_id")

    raw_paragraphs = payload.get("paragraphs")
    if not isinstance(raw_paragraphs, list) or not raw_paragraphs:
        raise ValueError("provider output must contain paragraphs")

    paragraphs: list[ParagraphUnit] = []
    for ordinal, raw_paragraph in enumerate(raw_paragraphs):
        if not isinstance(raw_paragraph, dict):
            raise ValueError("paragraph must be an object")
        raw_sentences = raw_paragraph.get("sentences")
        if not isinstance(raw_sentences, list) or not raw_sentences:
            raise ValueError("paragraph must contain sentences")

        sentences: list[SentenceUnit] = []
        for raw_sentence in raw_sentences:
            if not isinstance(raw_sentence, dict):
                raise ValueError("sentence must be an object")
            text_value = raw_sentence.get("text")
            if not isinstance(text_value, str) or not text_value.strip():
                raise ValueError("sentence text must be non-empty")

            evidence_refs = raw_sentence.get("evidence_refs") or []
            citation_refs = raw_sentence.get("citation_refs") or []
            if (
                not isinstance(evidence_refs, list)
                or not all(isinstance(x, str) for x in evidence_refs)
            ):
                raise ValueError("evidence_refs must be a string list")
            if (
                not isinstance(citation_refs, list)
                or not all(isinstance(x, str) for x in citation_refs)
            ):
                raise ValueError("citation_refs must be a string list")

            sentences.append(SentenceUnit(
                text=text_value.strip(),
                char_start=0,
                char_end=0,
                evidence_refs=evidence_refs,
                citation_refs=citation_refs,
            ))

        paragraph = _make_paragraph(ordinal, sentences)
        if paragraph is not None:
            paragraphs.append(paragraph)

    if not paragraphs:
        raise ValueError("provider output produced no paragraphs")
    return paragraphs


def _provider_generate(
    *,
    contract: SectionContract,
    packet: EvidencePacket,
) -> tuple[list[ParagraphUnit], str, str]:
    provider, profile = _build_provider()
    user_prompt = build_prompt(contract=contract, packet=packet)
    result = provider.generate(
        system_prompt=SYSTEM_CONTRACT,
        user_prompt=user_prompt,
        temperature=profile.temperature,
        max_output_tokens=profile.max_output_tokens,
    )
    paragraphs = _parse_provider_output(
        raw_text=result.text,
        contract=contract,
    )
    return paragraphs, result.provider, result.model


def generate_section(
    db: Session,
    *,
    contract: SectionContract,
    packet: EvidencePacket,
    mode: str,
) -> GeneratedSection:
    _ = db
    warnings: list[str] = []

    if mode not in (
        ProseGenerationMode.DETERMINISTIC.value,
        ProseGenerationMode.HYBRID.value,
        ProseGenerationMode.PROVIDER_ASSISTED.value,
    ):
        warnings.append(f"unknown_mode_fallback:{mode}")
        mode = ProseGenerationMode.DETERMINISTIC.value

    provider_name: str | None = None
    model_name: str | None = None

    if mode == ProseGenerationMode.DETERMINISTIC.value:
        paragraphs, dwarn = _deterministic_generate(
            contract=contract,
            packet=packet,
        )
        warnings.extend(dwarn)
        mode_used = mode
    else:
        try:
            paragraphs, provider_name, model_name = _provider_generate(
                contract=contract, packet=packet
            )
            mode_used = ProseGenerationMode.PROVIDER_ASSISTED.value
        except (GenerationProviderError, ProviderResolutionError, ValueError):
            if mode == ProseGenerationMode.PROVIDER_ASSISTED.value:
                raise
            logger.warning(
                "m28_5_provider_fallback section=%s",
                contract.section_key,
                exc_info=True,
            )
            paragraphs, dwarn = _deterministic_generate(
                contract=contract,
                packet=packet,
            )
            warnings.append("provider_fallback")
            warnings.extend(dwarn)
            mode_used = ProseGenerationMode.DETERMINISTIC.value

    unit = SectionUnit(
        section_key=contract.section_key,
        section_type=contract.section_type,
        display_order=contract.display_order,
        title=contract.title,
        paragraphs=paragraphs,
        provenance={
            "mode_used": mode_used,
            "provider": provider_name,
            "model": model_name,
            "m28_evidence_count": len(packet.m28_items),
            "technical_fact_count": len(packet.technical_facts),
            "experiment_result_count": len(packet.experiment_results),
            "metric_count": len(packet.metrics),
            "citation_candidate_count": len(packet.citation_candidates),
        },
        warnings=list(warnings),
    )
    return GeneratedSection(
        unit=unit,
        mode_used=mode_used,
        warnings=warnings,
        provider_name=provider_name,
        model_name=model_name,
    )


__all__ = ["GeneratedSection", "generate_section"]
