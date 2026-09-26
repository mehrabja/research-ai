"""M28 — Contract validation + hash tests (no DB)."""
from __future__ import annotations

import pytest

from app.core.exceptions import SectionResearchContractInvalid
from app.services.section_research import contract as c_svc


def _valid_contract(section_key: str = "introduction") -> dict:
    return {
        "section_key": section_key,
        "research_objective": "introduction: Frame the problem.",
        "retrieval_intents": ["background", "recent_evidence"],
        "evidence_requirements": [
            {
                "requirement_id": "00000000-0000-0000-0000-000000000001",
                "requirement_key": "intro.background",
                "requirement_type": "background",
                "required": True,
                "priority": 7,
                "min_sources": 3,
                "max_sources": None,
                "preferred_paper_types": [],
                "preferred_research_designs": [],
                "max_age_years": None,
                "full_text_required": False,
                "min_relevance_score": None,
                "coverage_weight": 1.0,
                "retrieval_intents": ["background"],
            },
        ],
        "source_constraints": {
            "min_sources": 3,
            "max_sources": None,
            "preferred_paper_types": [],
            "preferred_research_designs": [],
            "max_age_years": None,
            "full_text_required": False,
            "min_relevance_score": None,
        },
        "coverage_target": 0.7,
        "citation_required": True,
        "intent_mapping_version": "m27-intent-v1",
    }


# ---------- valid path ----------


def test_validate_contract_accepts_valid_payload():
    vc = c_svc.validate_contract(
        contract=_valid_contract(), section_key="introduction"
    )
    assert vc.section_key == "introduction"
    assert vc.research_objective.startswith("introduction:")
    assert vc.retrieval_intents == ("background", "recent_evidence")
    assert len(vc.evidence_requirements) == 1
    assert vc.coverage_target == 0.7
    assert vc.citation_required is True
    assert vc.intent_mapping_version == "m27-intent-v1"
    assert isinstance(vc.contract_hash, str)
    assert len(vc.contract_hash) == 32


def test_validate_contract_deduplicates_intents():
    c = _valid_contract()
    c["retrieval_intents"] = ["background", "background", "recent_evidence"]
    vc = c_svc.validate_contract(contract=c, section_key="introduction")
    assert vc.retrieval_intents == ("background", "recent_evidence")


# ---------- invalid paths ----------


def test_validate_contract_rejects_empty():
    with pytest.raises(SectionResearchContractInvalid):
        c_svc.validate_contract(contract={}, section_key="introduction")


def test_validate_contract_rejects_missing_section_key():
    c = _valid_contract()
    del c["section_key"]
    with pytest.raises(SectionResearchContractInvalid):
        c_svc.validate_contract(contract=c, section_key="introduction")


def test_validate_contract_rejects_section_key_mismatch():
    c = _valid_contract("introduction")
    with pytest.raises(SectionResearchContractInvalid):
        c_svc.validate_contract(contract=c, section_key="methods")


def test_validate_contract_rejects_empty_objective():
    c = _valid_contract()
    c["research_objective"] = "   "
    with pytest.raises(SectionResearchContractInvalid):
        c_svc.validate_contract(contract=c, section_key="introduction")


def test_validate_contract_rejects_unknown_intent():
    c = _valid_contract()
    c["retrieval_intents"] = ["background", "made_up_intent"]
    with pytest.raises(SectionResearchContractInvalid):
        c_svc.validate_contract(contract=c, section_key="introduction")


def test_validate_contract_rejects_unknown_intent_in_requirement():
    c = _valid_contract()
    c["evidence_requirements"][0]["retrieval_intents"] = ["not_an_intent"]
    with pytest.raises(SectionResearchContractInvalid):
        c_svc.validate_contract(contract=c, section_key="introduction")


def test_validate_contract_rejects_required_requirement_without_intents():
    c = _valid_contract()
    c["evidence_requirements"][0]["retrieval_intents"] = []
    with pytest.raises(SectionResearchContractInvalid):
        c_svc.validate_contract(contract=c, section_key="introduction")


def test_validate_contract_rejects_missing_intent_mapping_version():
    c = _valid_contract()
    del c["intent_mapping_version"]
    with pytest.raises(SectionResearchContractInvalid):
        c_svc.validate_contract(contract=c, section_key="introduction")


def test_validate_contract_rejects_unsupported_intent_mapping_version():
    c = _valid_contract()
    c["intent_mapping_version"] = "m99-intent-v9"
    with pytest.raises(SectionResearchContractInvalid):
        c_svc.validate_contract(contract=c, section_key="introduction")


def test_validate_contract_rejects_invalid_coverage_target():
    c = _valid_contract()
    c["coverage_target"] = 1.5
    with pytest.raises(SectionResearchContractInvalid):
        c_svc.validate_contract(contract=c, section_key="introduction")


def test_validate_contract_rejects_boolean_coverage_target():
    c = _valid_contract()
    c["coverage_target"] = True
    with pytest.raises(SectionResearchContractInvalid):
        c_svc.validate_contract(contract=c, section_key="introduction")


def test_validate_contract_rejects_missing_requirement_key_field():
    c = _valid_contract()
    del c["evidence_requirements"][0]["requirement_key"]
    with pytest.raises(SectionResearchContractInvalid):
        c_svc.validate_contract(contract=c, section_key="introduction")


def test_validate_contract_rejects_non_dict_source_constraints():
    c = _valid_contract()
    c["source_constraints"] = "not a dict"
    with pytest.raises(SectionResearchContractInvalid):
        c_svc.validate_contract(contract=c, section_key="introduction")


# ---------- hash determinism ----------


def test_contract_hash_is_deterministic():
    c = _valid_contract()
    h1 = c_svc.compute_contract_hash(c)
    h2 = c_svc.compute_contract_hash(c)
    assert h1 == h2
    assert len(h1) == 32


def test_contract_hash_ignores_dict_key_order():
    c1 = _valid_contract()
    c2 = {
        "citation_required": c1["citation_required"],
        "coverage_target": c1["coverage_target"],
        "intent_mapping_version": c1["intent_mapping_version"],
        "source_constraints": c1["source_constraints"],
        "evidence_requirements": c1["evidence_requirements"],
        "retrieval_intents": c1["retrieval_intents"],
        "research_objective": c1["research_objective"],
        "section_key": c1["section_key"],
    }
    assert c_svc.compute_contract_hash(c1) == c_svc.compute_contract_hash(c2)


def test_contract_hash_changes_on_semantic_change():
    c1 = _valid_contract()
    c2 = _valid_contract()
    c2["research_objective"] = "different objective"
    assert c_svc.compute_contract_hash(c1) != c_svc.compute_contract_hash(c2)


def test_contract_hash_changes_on_intent_change():
    c1 = _valid_contract()
    c2 = _valid_contract()
    c2["retrieval_intents"] = ["background"]
    assert c_svc.compute_contract_hash(c1) != c_svc.compute_contract_hash(c2)
