from unittest.mock import MagicMock

from app.services.research_planning import refinement as ref


def test_parse_rejects_unknown_section():
    out = ref.parse_and_validate_refinement(
        raw={
            "sections": [{"section_key": "does_not_exist"}],
            "evidence_requirements": [],
            "budget_adjustments": {},
        },
        allowed_section_keys={"introduction"},
        allowed_requirement_keys=set(),
    )
    assert out is None


def test_parse_rejects_bad_json():
    out = ref.parse_and_validate_refinement(
        raw="not json",
        allowed_section_keys={"introduction"},
        allowed_requirement_keys=set(),
    )
    assert out is None


def test_parse_rejects_negative_budget():
    out = ref.parse_and_validate_refinement(
        raw={
            "sections": [],
            "evidence_requirements": [],
            "budget_adjustments": {"introduction": -0.5},
        },
        allowed_section_keys={"introduction"},
        allowed_requirement_keys=set(),
    )
    assert out is None


def test_parse_accepts_valid():
    out = ref.parse_and_validate_refinement(
        raw={
            "sections": [
                {"section_key": "introduction", "title": "New"}
            ],
            "evidence_requirements": [],
            "budget_adjustments": {"introduction": 0.2},
        },
        allowed_section_keys={"introduction"},
        allowed_requirement_keys=set(),
    )
    assert out is not None


def test_call_provider_with_complete_json():
    provider = MagicMock()
    provider.complete_json.return_value = {"ok": True}
    assert ref.call_refinement_provider(provider, "p") == {"ok": True}
