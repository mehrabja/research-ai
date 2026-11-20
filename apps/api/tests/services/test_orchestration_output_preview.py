from __future__ import annotations

import json

from app.schemas.orchestration import build_orchestration_output_preview


def test_output_preview_removes_credentials_recursively() -> None:
    preview = build_orchestration_output_preview(
        {
            "status": "complete",
            "reviewers": [
                {
                    "name": "Evidence auditor",
                    "assessment": "Supported by the cited excerpts",
                    "api_key": "must-not-leak",
                    "credentials": {"access_token": "also-secret"},
                }
            ],
            "authorization": "Bearer do-not-return",
            "_internal_trace": {"private_key": "private"},
        }
    )

    assert preview is not None
    assert preview["status"] == "complete"
    reviewer = preview["reviewers"][0]
    assert reviewer["assessment"] == "Supported by the cited excerpts"
    assert "api_key" not in reviewer
    assert "credentials" not in reviewer
    assert "authorization" not in preview
    assert "_internal_trace" not in preview
    assert "must-not-leak" not in json.dumps(preview)
    assert "also-secret" not in json.dumps(preview)


def test_output_preview_bounds_lists_strings_and_nesting() -> None:
    preview = build_orchestration_output_preview(
        {
            "items": list(range(100)),
            "long_text": "x" * 5000,
            "nested": {"a": {"b": {"c": {"d": {"e": "too deep"}}}}},
        }
    )

    assert preview is not None
    assert len(preview["items"]) <= 25
    assert len(preview["long_text"]) <= 912
    assert preview["nested"]["a"]["b"]["c"]["d"] == "[nested content omitted]"
    encoded = json.dumps(preview, ensure_ascii=False).encode("utf-8")
    assert len(encoded) <= 16_000


def test_output_preview_omits_empty_or_non_object_snapshots() -> None:
    assert build_orchestration_output_preview(None) is None
    assert build_orchestration_output_preview([]) is None
    assert build_orchestration_output_preview({}) is None


def test_output_preview_caps_large_payloads() -> None:
    preview = build_orchestration_output_preview(
        {"sections": [{"text": "evidence " * 700} for _ in range(80)]}
    )

    assert preview is not None
    encoded = json.dumps(preview, ensure_ascii=False).encode("utf-8")
    assert len(encoded) <= 16_000
