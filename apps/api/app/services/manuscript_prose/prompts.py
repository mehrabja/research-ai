"""M28.5 — Prompt construction from structured components."""
from __future__ import annotations

import json

from app.domain.manuscript_prose import PROSE_PROMPT_VERSION
from app.services.manuscript_prose.contracts import SectionContract
from app.services.manuscript_prose.evidence import EvidencePacket

SYSTEM_CONTRACT = """\
You are a scientific manuscript prose writer. You write ONLY from the
evidence provided below. You MUST NOT invent:
  * citations, references, or DOIs
  * numerical results, metrics, or measurements
  * dataset names, tool names, or model names
  * methodology details not present in the evidence
  * claims stronger than the evidence supports.

If evidence is missing for a required point, state that no supported
evidence is available instead of speculating. Distinguish observed
facts from inference. Preserve the strength of every evidence item.
Output MUST be valid JSON matching the requested schema.
"""


def _evidence_block(packet: EvidencePacket) -> str:
    lines: list[str] = []
    lines.append("### M28 SECTION RESEARCH EVIDENCE")
    if not packet.m28_items:
        lines.append("(no M28 evidence available for this section)")
    for e in packet.m28_items:
        lines.append(
            f"- evidence_id={e.evidence_id} role={e.evidence_role} "
            f"rank={e.rank} excerpt={e.excerpt!r}"
        )
    lines.append("")
    lines.append("### M29 TECHNICAL FACTS")
    if not packet.technical_facts:
        lines.append("(no technical facts available)")
    for f in packet.technical_facts:
        lines.append(
            f"- fact_id={f.fact_id} type={f.fact_type} "
            f"key={f.fact_key} value={f.fact_value!r}"
        )
    lines.append("")
    lines.append("### M29 EXPERIMENT RESULTS")
    if not packet.experiment_results:
        lines.append("(no experiment results available)")
    for r in packet.experiment_results:
        lines.append(
            f"- result_id={r.result_id} type={r.result_type} "
            f"name={r.name!r} key={r.experiment_key!r}"
        )
    lines.append("")
    lines.append("### M29 METRICS")
    if not packet.metrics:
        lines.append("(no metrics available)")
    for m in packet.metrics:
        lines.append(
            f"- metric_id={m.metric_id} name={m.name!r} "
            f"value_numeric={m.value_numeric} "
            f"value_text={m.value_text!r} unit={m.unit!r} "
            f"split={m.split!r} direction={m.direction!r}"
        )
    lines.append("")
    lines.append("### EXISTING CITATION CANDIDATES (opt-in by id)")
    if not packet.citation_candidates:
        lines.append("(no citation identities available)")
    for c in packet.citation_candidates:
        lines.append(
            f"- identity_id={c.identity_id} "
            f"source_id={c.source_id} label={c.display_label!r}"
        )
    return "\n".join(lines)


OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["section_id", "paragraphs"],
    "properties": {
        "section_id": {"type": "string"},
        "paragraphs": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["sentences"],
                "properties": {
                    "sentences": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["text"],
                            "properties": {
                                "text": {"type": "string"},
                                "evidence_refs": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "citation_refs": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}


def build_prompt(
    *,
    contract: SectionContract,
    packet: EvidencePacket,
) -> str:
    schema_blob = json.dumps(
        OUTPUT_SCHEMA, indent=2, sort_keys=True,
    )
    parts = [
        SYSTEM_CONTRACT,
        "",
        "### SECTION CONTRACT",
        json.dumps(
            {
                "section_key": contract.section_key,
                "section_type": contract.section_type,
                "title": contract.title,
                "purpose": contract.purpose,
                "research_objective": contract.research_objective,
                "retrieval_intents": contract.retrieval_intents,
                "requirement_keys": contract.requirement_keys,
                "citation_required": contract.citation_required,
                "word_budget": contract.word_budget,
            },
            indent=2,
            sort_keys=True,
        ),
        "",
        _evidence_block(packet),
        "",
        "### OUTPUT SCHEMA",
        schema_blob,
        "",
        "### RULES",
        "- Use only supplied evidence identifiers in evidence_refs.",
        "- Use only supplied identity_id values in citation_refs.",
        "- If evidence is missing, produce a sentence that explicitly "
        "states no supported evidence is available.",
        "- Do not invent any reference to figures, tables, or datasets.",
        "- Preserve all numeric values and units exactly as given.",
    ]
    return "\n".join(parts)


__all__ = [
    "SYSTEM_CONTRACT",
    "OUTPUT_SCHEMA",
    "build_prompt",
    "PROSE_PROMPT_VERSION",
]
