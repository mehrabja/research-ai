"""M29 — Deterministic technical fact extraction from M20 artifacts."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.code_analysis import (
    CodeAnalysis,
    CodeDependency,
    CodeSymbol,
)
from app.db.models.data_profile import DataColumnProfile, DataProfile
from app.domain.technical_intelligence import (
    CONF_DEPENDENCY,
    CONF_EXACT,
    CONF_KEYWORD_HEURISTIC,
    CONF_NAME_PATTERN_HEURISTIC,
    M29_VERSION,
    TECHNICAL_EXTRACTION_VERSION,
    TechnicalFactType,
    is_algorithm_name,
    scan_hyperparameters_from_signature,
)


@dataclass
class ExtractedFact:
    project_id: uuid.UUID
    report_id: uuid.UUID | None
    manuscript_version_id: uuid.UUID | None
    project_file_id: uuid.UUID
    code_analysis_id: uuid.UUID | None
    data_profile_id: uuid.UUID | None
    fact_type: str
    fact_key: str
    fact_value: str | None
    normalized_value: str | None
    unit: str | None
    confidence: float
    provenance: dict
    status: str = "extracted"


_PIPELINE_SUFFIXES = (
    "_step", "_stage", "_pipeline", "_run", "_process",
    "_execute", "_train", "_evaluate", "_predict", "_build",
)
_IO_INPUT_NAMES = {"input", "inputs", "src", "source", "in_path", "in_file"}
_IO_OUTPUT_NAMES = {"output", "outputs", "dst", "destination",
                    "out_path", "out_file"}


def _norm_key(name: str) -> str:
    return "".join(
        c if c.isalnum() else "_" for c in name.lower()
    ).strip("_")


def _is_pipeline_step(name: str) -> bool:
    if not name:
        return False
    low = name.lower()
    return any(low.endswith(s) for s in _PIPELINE_SUFFIXES)


def _func_param_names(signature: str) -> tuple[str, ...]:
    if not signature:
        return ()
    a = signature.find("(")
    b = signature.rfind(")")
    if a < 0 or b <= a:
        return ()
    inner = signature[a + 1:b]
    names: list[str] = []
    for token in inner.split(","):
        token = token.strip()
        if not token or token in ("self", "cls"):
            continue
        if ":" in token:
            token = token.split(":", 1)[0].strip()
        if "=" in token:
            token = token.split("=", 1)[0].strip()
        token = token.lstrip("*").strip()
        if token:
            names.append(token)
    return tuple(names)


def extract_from_code_analysis(
    db: Session,
    *,
    analysis: CodeAnalysis,
    project_id: uuid.UUID,
    report_id: uuid.UUID | None,
    manuscript_version_id: uuid.UUID | None,
    max_facts: int,
    context_hash: str,
) -> list[ExtractedFact]:
    facts: list[ExtractedFact] = []
    parser = analysis.parser or "m20"
    parser_version = (
        analysis.parser_version or analysis.analysis_version or "m20"
    )
    base_prov: dict[str, Any] = {
        "artifact_id": str(analysis.project_file_id),
        "code_analysis_id": str(analysis.id),
        "parser": parser,
        "parser_version": parser_version,
        "m29_version": M29_VERSION,
        "extraction_version": TECHNICAL_EXTRACTION_VERSION,
        "context_hash": context_hash,
     }
    symbols = list(db.execute(
        select(CodeSymbol)
        .where(CodeSymbol.code_analysis_id == analysis.id)
        .order_by(CodeSymbol.line_start.asc(), CodeSymbol.id.asc())
    ).scalars().all())

    deps = list(db.execute(
        select(CodeDependency)
        .where(CodeDependency.code_analysis_id == analysis.id)
        .order_by(CodeDependency.id.asc())
    ).scalars().all())

    def _emit(
        ftype: str, name: str, confidence: float, kind: str,
        *, value: str | None = None, symbol_id: str | None = None,
    ) -> None:
        prov = dict(base_prov)
        prov["kind"] = kind
        if symbol_id:
            prov["symbol_id"] = symbol_id
        facts.append(ExtractedFact(
            project_id=project_id, report_id=report_id,
            manuscript_version_id=manuscript_version_id,
            project_file_id=analysis.project_file_id,
            code_analysis_id=analysis.id, data_profile_id=None,
            fact_type=ftype,
            fact_key=_norm_key(name),
            fact_value=value if value is not None else name,
            normalized_value=_norm_key(name),
            unit=None, confidence=confidence, provenance=prov,
        ))

    for s in symbols:
        if len(facts) >= max_facts:
            break
        name = s.name or ""
        if not name:
            continue

        if s.symbol_type == "class":
            _emit(TechnicalFactType.CLASS.value, name, CONF_EXACT,
                  "symbol.class", symbol_id=str(s.id))

        if s.symbol_type in ("function", "method"):
            _emit(TechnicalFactType.FUNCTION.value, name, CONF_EXACT,
                  "symbol.function", symbol_id=str(s.id))

        if s.symbol_type in ("class", "function", "method") and (
            is_algorithm_name(name)
        ):
            _emit(TechnicalFactType.ALGORITHM.value, name,
                  CONF_KEYWORD_HEURISTIC, "algorithm",
                  symbol_id=str(s.id))

        if _is_pipeline_step(name):
            _emit(TechnicalFactType.PIPELINE_STEP.value, name,
                  CONF_KEYWORD_HEURISTIC, "pipeline_step",
                  symbol_id=str(s.id))

        if s.symbol_type in ("function", "method") and s.signature:
            for hp in scan_hyperparameters_from_signature(s.signature):
                if len(facts) >= max_facts:
                    break
                prov = dict(base_prov)
                prov["kind"] = "hyperparameter"
                prov["symbol_id"] = str(s.id)
                facts.append(ExtractedFact(
                    project_id=project_id, report_id=report_id,
                    manuscript_version_id=manuscript_version_id,
                    project_file_id=analysis.project_file_id,
                    code_analysis_id=analysis.id, data_profile_id=None,
                    fact_type=TechnicalFactType.HYPERPARAMETER.value,
                    fact_key=hp, fact_value=None,
                    normalized_value=hp, unit=None,
                    confidence=CONF_EXACT, provenance=prov,
                ))
            params = _func_param_names(s.signature)
            in_refs = [p for p in params if p in _IO_INPUT_NAMES]
            out_refs = [p for p in params if p in _IO_OUTPUT_NAMES]
            if in_refs:
                _emit(TechnicalFactType.INPUT_REFERENCE.value, name,
                      CONF_NAME_PATTERN_HEURISTIC, "input_reference",
                      value=",".join(in_refs), symbol_id=str(s.id))
            if out_refs:
                _emit(TechnicalFactType.OUTPUT_REFERENCE.value, name,
                      CONF_NAME_PATTERN_HEURISTIC, "output_reference",
                      value=",".join(out_refs), symbol_id=str(s.id))

    for d in deps:
        if len(facts) >= max_facts:
            break
        if not d.dependency_name:
            continue
        prov = dict(base_prov)
        prov["kind"] = "dependency"
        prov["dependency_id"] = str(d.id)
        prov["dependency_type"] = d.dependency_type
        prov["line_number"] = d.line_number
        if d.dependency_type in ("import", "from_import"):
            ftype = TechnicalFactType.IMPORT.value
        else:
            ftype = TechnicalFactType.LIBRARY.value
        facts.append(ExtractedFact(
            project_id=project_id, report_id=report_id,
            manuscript_version_id=manuscript_version_id,
            project_file_id=analysis.project_file_id,
            code_analysis_id=analysis.id, data_profile_id=None,
            fact_type=ftype,
            fact_key=_norm_key(d.dependency_name),
            fact_value=d.dependency_name,
            normalized_value=_norm_key(d.dependency_name),
            unit=None, confidence=CONF_DEPENDENCY, provenance=prov,
        ))

    return facts


def extract_from_data_profile(
    db: Session,
    *,
    profile: DataProfile,
    project_id: uuid.UUID,
    report_id: uuid.UUID | None,
    manuscript_version_id: uuid.UUID | None,
    max_facts: int,
    context_hash: str,
) -> list[ExtractedFact]:
    facts: list[ExtractedFact] = []
    base_prov = {
        "artifact_id": str(profile.project_file_id),
        "data_profile_id": str(profile.id),
        "parser": "m20_data_profile",
        "parser_version": profile.profile_version or "m20",
        "format": profile.format,
        "m29_version": M29_VERSION,
        "extraction_version": TECHNICAL_EXTRACTION_VERSION,
        "context_hash": context_hash,
    }

    for key, val in (
        ("format", profile.format),
        ("row_count", str(profile.row_count)
         if profile.row_count is not None else None),
        ("column_count", str(profile.column_count)
         if profile.column_count is not None else None),
    ):
        if val is None:
            continue
        facts.append(ExtractedFact(
            project_id=project_id, report_id=report_id,
            manuscript_version_id=manuscript_version_id,
            project_file_id=profile.project_file_id,
            code_analysis_id=None, data_profile_id=profile.id,
            fact_type=TechnicalFactType.DATASET_CHARACTERISTIC.value,
            fact_key=key, fact_value=val, normalized_value=val,
            unit=None, confidence=CONF_EXACT,
            provenance={**base_prov, "kind": f"profile.{key}"},
        ))

    columns = list(db.execute(
        select(DataColumnProfile)
        .where(DataColumnProfile.data_profile_id == profile.id)
        .order_by(DataColumnProfile.ordinal.asc())
    ).scalars().all())

    for c in columns:
        if len(facts) >= max_facts:
            break
        facts.append(ExtractedFact(
            project_id=project_id, report_id=report_id,
            manuscript_version_id=manuscript_version_id,
            project_file_id=profile.project_file_id,
            code_analysis_id=None, data_profile_id=profile.id,
            fact_type=TechnicalFactType.DATASET_COLUMN.value,
            fact_key=_norm_key(c.name),
            fact_value=c.name, normalized_value=c.name,
            unit=None, confidence=CONF_EXACT,
            provenance={
                **base_prov, "kind": "profile.column",
                "column_id": str(c.id), "column_name": c.name,
                "ordinal": c.ordinal,
                "inferred_type": c.inferred_type,
            },
        ))
    return facts


__all__ = [
    "ExtractedFact",
    "extract_from_code_analysis",
    "extract_from_data_profile",
]
