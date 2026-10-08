"""Prompt includes all config fields; omits None."""
from __future__ import annotations

import uuid

from app.domain.generation import EvidenceItem, EvidenceSet
from app.services.generation_prompt import build_user_prompt


def _ev() -> EvidenceSet:
    sid = uuid.uuid4()
    cid = uuid.uuid4()
    return EvidenceSet(items=(
        EvidenceItem(
            rank=1, marker="[E1]",
            evidence_id=f"source:{sid}:chunk:{cid}",
            source_id=sid, chunk_id=cid,
            content="x", fusion_score=0.5,
        ),
    ))


def test_prompt_contains_all_config_fields() -> None:
    p = build_user_prompt(
        topic="My Topic", output_language="fa", domain="biology",
        audience_level="expert", tone="formal", length="long",
        structure_template="IMRaD", evidence=_ev(),
    )
    assert "Topic: My Topic" in p
    assert "Output language: fa" in p
    assert "Tone: formal" in p
    assert "Target length: long" in p
    assert "Template: IMRaD" in p


def test_prompt_includes_user_generation_brief() -> None:
    p = build_user_prompt(
        topic="T", output_language="en", domain=None, audience_level=None,
        tone=None, length=None, structure_template=None, evidence=_ev(),
        brief="Focus the draft on the limitations and comparison with prior work.",
    )
    assert "=== USER GENERATION BRIEF ===" in p
    assert "Focus the draft on the limitations" in p


def test_prompt_omits_missing_config() -> None:
    p = build_user_prompt(
        topic="T", output_language="en", domain=None, audience_level=None,
        tone=None, length=None, structure_template=None, evidence=_ev(),
    )
    assert "=== STYLE ===" not in p
    assert "=== LENGTH ===" not in p
    assert "=== STRUCTURE ===" not in p
