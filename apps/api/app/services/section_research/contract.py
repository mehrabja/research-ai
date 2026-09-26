"""M28 — Contract validation + deterministic contract hash."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from app.core.exceptions import SectionResearchContractInvalid
from app.domain.manuscript import KNOWN_RETRIEVAL_INTENTS
from app.domain.section_research import (
    SECTION_RESEARCH_CONTRACT_VERSION,
    SUPPORTED_CONTRACT_INTENT_MAPPING_VERSIONS,
)

_REQUIRED_REQ_KEYS = (
    "requirement_id",
    "requirement_key",
    "requirement_type",
    "required",
    "retrieval_intents",
)


@dataclass(frozen=True)
class ValidatedContract:
    section_key: str
    research_objective: str
    retrieval_intents: tuple[str, ...]
    evidence_requirements: tuple[dict[str, Any], ...]
    source_constraints: dict[str, Any]
    coverage_target: float
    citation_required: bool
    intent_mapping_version: str
    contract_hash: str


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def compute_contract_hash(contract: dict[str, Any]) -> str:
    payload = _canonical_json(contract)
    h = hashlib.sha256()
    h.update(SECTION_RESEARCH_CONTRACT_VERSION.encode("utf-8"))
    h.update(b"\x00")
    h.update(payload.encode("utf-8"))
    return h.hexdigest()[:32]


def validate_contract(
    *,
    contract: dict[str, Any],
    section_key: str,
) -> ValidatedContract:
    if not isinstance(contract, dict) or not contract:
        raise SectionResearchContractInvalid("empty research contract")

    ck = contract.get("section_key")
    if not isinstance(ck, str) or not ck:
        raise SectionResearchContractInvalid(
            "missing section_key in research contract"
        )
    if ck != section_key:
        raise SectionResearchContractInvalid(
            f"contract section_key {ck!r} != section {section_key!r}"
        )

    obj = contract.get("research_objective")
    if not isinstance(obj, str) or not obj.strip():
        raise SectionResearchContractInvalid(
            "missing or empty research_objective"
        )

    imv = contract.get("intent_mapping_version")
    if imv not in SUPPORTED_CONTRACT_INTENT_MAPPING_VERSIONS:
        raise SectionResearchContractInvalid(
            f"unsupported intent_mapping_version {imv!r}"
        )

    intents_raw = contract.get("retrieval_intents") or []
    if not isinstance(intents_raw, list):
        raise SectionResearchContractInvalid(
            "retrieval_intents must be a list"
        )
    seen: set[str] = set()
    intents_norm: list[str] = []
    for i in intents_raw:
        if not isinstance(i, str):
            raise SectionResearchContractInvalid(
                f"intent must be str, got {type(i).__name__}"
            )
        if i not in KNOWN_RETRIEVAL_INTENTS:
            raise SectionResearchContractInvalid(f"unknown intent {i!r}")
        if i not in seen:
            seen.add(i)
            intents_norm.append(i)

    reqs_raw = contract.get("evidence_requirements") or []
    if not isinstance(reqs_raw, list):
        raise SectionResearchContractInvalid(
            "evidence_requirements must be a list"
        )
    reqs_norm: list[dict[str, Any]] = []
    for idx, r in enumerate(reqs_raw):
        if not isinstance(r, dict):
            raise SectionResearchContractInvalid(
                f"requirement[{idx}] must be an object"
            )
        for k in _REQUIRED_REQ_KEYS:
            if k not in r:
                raise SectionResearchContractInvalid(
                    f"requirement[{idx}] missing {k!r}"
                )
        rk = r["requirement_key"]
        if not isinstance(rk, str) or not rk:
            raise SectionResearchContractInvalid(
                f"requirement[{idx}] invalid requirement_key"
            )
        r_intents = r.get("retrieval_intents") or []
        if not isinstance(r_intents, list):
            raise SectionResearchContractInvalid(
                f"requirement {rk}: retrieval_intents must be list"
            )
        for i in r_intents:
            if i not in KNOWN_RETRIEVAL_INTENTS:
                raise SectionResearchContractInvalid(
                    f"requirement {rk}: unknown intent {i!r}"
                )
        if bool(r.get("required")) and not r_intents:
            raise SectionResearchContractInvalid(
                f"required requirement {rk} has no intent mapping"
            )
        reqs_norm.append(r)

    sc = contract.get("source_constraints")
    if not isinstance(sc, dict):
        raise SectionResearchContractInvalid(
            "source_constraints must be an object"
        )

    ct = contract.get("coverage_target")
    if (
        not isinstance(ct, (int, float))
        or isinstance(ct, bool)
        or not (0.0 <= float(ct) <= 1.0)
    ):
        raise SectionResearchContractInvalid(
            "coverage_target must be a float in [0, 1]"
        )

    cr = contract.get("citation_required")
    if not isinstance(cr, bool):
        raise SectionResearchContractInvalid(
            "citation_required must be a bool"
        )

    return ValidatedContract(
        section_key=ck,
        research_objective=obj,
        retrieval_intents=tuple(intents_norm),
        evidence_requirements=tuple(reqs_norm),
        source_constraints=sc,
        coverage_target=float(ct),
        citation_required=cr,
        intent_mapping_version=imv,
        contract_hash=compute_contract_hash(contract),
    )


__all__ = [
    "ValidatedContract",
    "compute_contract_hash",
    "validate_contract",
]
