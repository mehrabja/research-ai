from __future__ import annotations

from app.services.agent_runtime import (
    build_agent_runtime_prompts,
    constrain_citations,
)


def test_prompt_builder_bounds_history_and_keeps_current_request() -> None:
    system, prompt = build_agent_runtime_prompts(
        report_topic="Cell signaling",
        report_domain="Molecular biology",
        history=[
            {"role": "user", "content": "Earlier question " + "x" * 4000},
            {"role": "assistant", "content": "Earlier answer"},
        ],
        current_message="Explain the limitations of this evidence.",
        evidence=[
            {
                "label": "E1",
                "reference": "source:s1:chunk:c1",
                "title": "Paper one",
                "page_number": 4,
                "excerpt": "A bounded excerpt.",
            }
        ],
        max_prompt_chars=24000,
    )
    assert "untrusted reference data" in system
    assert "Explain the limitations" in prompt
    assert "[E1]" in prompt
    assert len(prompt) <= 24000


def test_prompt_builder_respects_small_prompt_budget() -> None:
    _, prompt = build_agent_runtime_prompts(
        report_topic="T" * 500,
        report_domain="D" * 200,
        history=[{"role": "user", "content": "H" * 1800}],
        current_message="C" * 2000,
        evidence=[
            {
                "label": f"E{i}",
                "reference": f"source:s:chunk:{i}",
                "title": "Paper",
                "page_number": 1,
                "excerpt": "x" * 1200,
            }
            for i in range(1, 9)
        ],
        max_prompt_chars=2500,
    )
    assert len(prompt) <= 2500
    assert "Current user request:" in prompt
    assert "C" in prompt


def test_model_citations_are_limited_to_retrieved_evidence() -> None:
    answer, refs = constrain_citations(
        "Supported [E1]. Unfounded [E9].",
        [
            {
                "label": "E1",
                "reference": "source:source-id:chunk:chunk-id",
                "source_id": "source-id",
                "chunk_id": "chunk-id",
            }
        ],
    )
    assert answer == "Supported [E1]. Unfounded [unverified reference]."
    assert len(refs) == 1
    assert refs[0]["source_id"] == "source-id"


def test_model_citations_are_removed_when_no_evidence_exists() -> None:
    answer, refs = constrain_citations("Claim [E1].", [])
    assert answer == "Claim [unverified reference]."
    assert refs == []
