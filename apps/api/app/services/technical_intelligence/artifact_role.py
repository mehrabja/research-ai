"""M29 — Deterministic artifact-role detection.

Priority:
  1. file_kind from ProjectFile (domain: app/domain/file.py FileKind)
  2. filename hints (result / config) — bounded regex
  3. extension fallback (when file_kind is unknown)
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.db.models.project_file import ProjectFile

ROLE_SOURCE_CODE = "source_code"
ROLE_DATASET = "dataset"
ROLE_CONFIGURATION = "configuration"
ROLE_EXPERIMENT_RESULT = "experiment_result"
ROLE_SUPPLEMENTARY = "supplementary"
ROLE_UNKNOWN = "unknown"

# Mapping from FileKind (app/domain/file.py) → role.
_FILE_KIND_TO_ROLE: dict[str, str] = {
    "code": ROLE_SOURCE_CODE,
    "structured_data": ROLE_DATASET,
    "spreadsheet": ROLE_DATASET,
    "document": ROLE_SUPPLEMENTARY,
    "pdf": ROLE_SUPPLEMENTARY,
    "text": ROLE_SUPPLEMENTARY,
    "presentation": ROLE_SUPPLEMENTARY,
    "image": ROLE_SUPPLEMENTARY,
    "archive": ROLE_SUPPLEMENTARY,
    "unknown": ROLE_UNKNOWN,
}

# Data-like kinds where filename can promote to experiment_result / config.
_DATA_LIKE_KINDS: frozenset[str] = frozenset({
    "structured_data", "spreadsheet",
})

_CODE_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs",
    ".rb", ".php", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs",
    ".kt", ".swift", ".scala", ".sh", ".ps1", ".sql",
}
_DATA_EXTS = {
    ".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".xlsx",
    ".xls", ".parquet",
}
_CFG_EXTS = {".yaml", ".yml", ".toml", ".ini", ".cfg", ".env"}

_RESULT_HINTS = re.compile(
    r"(result|metrics?|eval|experiment|run|score|leaderboard|sweep)",
    re.IGNORECASE,
)
_CFG_HINTS = re.compile(
    r"(config|settings|hyper|param)", re.IGNORECASE,
)


@dataclass
class ArtifactRole:
    role: str
    reason: str


def _filename(pf: ProjectFile) -> str:
    return (
        getattr(pf, "original_filename", None)
        or getattr(pf, "normalized_filename", None)
        or ""
    )


def detect_artifact_role(pf: ProjectFile) -> ArtifactRole:
    fk = getattr(pf, "file_kind", None)
    name = _filename(pf)

    # 1) file_kind exact mapping
    if isinstance(fk, str):
        base_role = _FILE_KIND_TO_ROLE.get(fk.lower())
        if base_role is not None:
            if fk.lower() in _DATA_LIKE_KINDS and name:
                if _RESULT_HINTS.search(name):
                    return ArtifactRole(
                        role=ROLE_EXPERIMENT_RESULT,
                        reason=f"file_kind+name:{fk}",
                    )
                if _CFG_HINTS.search(name):
                    return ArtifactRole(
                        role=ROLE_CONFIGURATION,
                        reason=f"file_kind+name:{fk}",
                    )
            return ArtifactRole(role=base_role, reason=f"file_kind:{fk}")

    # 2) explicit metadata override (rare)
    meta = getattr(pf, "file_meta", None) or getattr(
        pf, "metadata", None
    ) or {}
    if isinstance(meta, dict):
        explicit = meta.get("artifact_role") or meta.get("file_role")
        if explicit in {
            ROLE_SOURCE_CODE, ROLE_DATASET, ROLE_CONFIGURATION,
            ROLE_EXPERIMENT_RESULT, ROLE_SUPPLEMENTARY,
        }:
            return ArtifactRole(role=str(explicit), reason="explicit_meta")

    # 3) extension fallback
    ext = (pf.extension or "").lower()
    if not ext and name:
        dot = name.rfind(".")
        if dot >= 0:
            ext = name[dot:].lower()

    if ext in _CODE_EXTS:
        return ArtifactRole(role=ROLE_SOURCE_CODE, reason="ext_code")
    if ext in _CFG_EXTS:
        return ArtifactRole(role=ROLE_CONFIGURATION, reason="ext_config")
    if ext in _DATA_EXTS:
        if _RESULT_HINTS.search(name or ""):
            return ArtifactRole(
                role=ROLE_EXPERIMENT_RESULT, reason="name_result_hint",
            )
        if _CFG_HINTS.search(name or ""):
            return ArtifactRole(
                role=ROLE_CONFIGURATION, reason="name_config_hint",
            )
        return ArtifactRole(role=ROLE_DATASET, reason="ext_data")
    return ArtifactRole(role=ROLE_UNKNOWN, reason="no_rule_matched")


def is_source_code(r: str) -> bool:
    return r == ROLE_SOURCE_CODE


def is_experiment_result(r: str) -> bool:
    return r == ROLE_EXPERIMENT_RESULT


def is_configuration(r: str) -> bool:
    return r == ROLE_CONFIGURATION


def is_dataset(r: str) -> bool:
    return r == ROLE_DATASET


__all__ = [
    "ArtifactRole", "detect_artifact_role",
    "is_source_code", "is_experiment_result",
    "is_configuration", "is_dataset",
    "ROLE_SOURCE_CODE", "ROLE_DATASET", "ROLE_CONFIGURATION",
    "ROLE_EXPERIMENT_RESULT", "ROLE_SUPPLEMENTARY", "ROLE_UNKNOWN",
]
