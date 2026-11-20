from __future__ import annotations

from app.services.orchestration.roundtable import (
    normalize_reviewer_response,
    normalize_synthesis_response,
    parse_model_json,
)


def test_parse_fenced_json_object() -> None:
    assert parse_model_json('```json\n{"assessment":"sound"}\n```') == {
        "assessment": "sound"
    }




def test_parse_rejects_top_level_array_even_when_it_contains_objects() -> None:
    assert parse_model_json('[{"assessment":"not a root object"}]') is None


def test_parse_json_object_after_explanatory_text() -> None:
    parsed = parse_model_json('Review: {"assessment":"limited"}')
    assert parsed == {"assessment": "limited"}


def test_parse_rejects_arrays_and_invalid_text() -> None:
    assert parse_model_json('[{"x":1}]') is None
    assert parse_model_json("not JSON") is None


def test_reviewer_filters_invented_evidence_references() -> None:
    normalized = normalize_reviewer_response(
        '{"assessment":"Supported in part","strengths":["Clear scope"],'
        '"risks":["Confounding"],"recommendations":["Pre-register"],'
        '"evidence_refs":["source:real","source:invented"]}',
        {"source:real"},
    )
    assert normalized["evidence_refs"] == ["source:real"]
    assert normalized["unsupported_evidence_refs"] == ["source:invented"]


def test_reviewer_unstructured_output_is_bounded() -> None:
    normalized = normalize_reviewer_response("x" * 5000, set())
    assert normalized["format_status"] == "unstructured"
    assert len(normalized["assessment"]) == 3000


def test_synthesis_preserves_disagreements_and_filters_refs() -> None:
    normalized = normalize_synthesis_response(
        '{"overall_assessment":"Mixed evidence","consensus":["Scope is clear"],'
        '"disagreements":["Causality is not established"],'
        '"priority_actions":["Validate externally"],"evidence_gaps":["No replication"],'
        '"risk_level":"high","evidence_refs":["source:real","source:fake"]}',
        {"source:real"},
    )
    assert normalized["risk_level"] == "high"
    assert normalized["disagreements"] == ["Causality is not established"]
    assert normalized["evidence_refs"] == ["source:real"]
    assert normalized["unsupported_evidence_refs"] == ["source:fake"]


def test_unknown_synthesis_risk_becomes_uncertain() -> None:
    normalized = normalize_synthesis_response(
        '{"overall_assessment":"Review","risk_level":"certain"}', set()
    )
    assert normalized["risk_level"] == "uncertain"
