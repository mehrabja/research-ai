"""M29 — Deterministic result parsing from RAW artifacts (bounded)."""
from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from app.db.models.project_file import ProjectFile
from app.domain.technical_intelligence import (
    M29_VERSION,
    RESULT_PARSER_VERSION,
    ExperimentResultType,
    is_known_metric_name,
    is_split_column,
    metric_direction,
    normalize_metric_name,
)

_ALLOWED_FORMATS = {"csv", "tsv", "json", "jsonl", "ndjson"}

_EXPERIMENT_KEY_CANDIDATES = (
    "experiment", "experiment_key", "experiment_id",
    "run", "run_id", "name", "model", "model_name",
    "config", "config_id", "id",
)


def _norm(n: str) -> str:
    return n.strip().lower()


def _detect_format(pf: ProjectFile) -> str | None:
    ext = (pf.extension or "").lower().lstrip(".")
    if ext in _ALLOWED_FORMATS:
        return "jsonl" if ext == "ndjson" else ext
    return None


def _pick(cols: Iterable[str], candidates: Iterable[str]) -> str | None:
    canon = {_norm(c): c for c in cols}
    for cand in candidates:
        if cand in canon:
            return canon[cand]
    return None


def _pick_split(cols: Iterable[str]) -> str | None:
    for c in cols:
        if is_split_column(c):
            return c
    return None


def _to_float(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


@dataclass
class ParsedMetric:
    name: str
    normalized_name: str
    value_numeric: float | None
    value_text: str | None
    unit: str | None
    split: str | None
    direction: str | None
    provenance: dict


@dataclass
class ParsedResult:
    result_type: str
    name: str
    experiment_key: str | None
    value: dict
    provenance: dict
    metrics: list[ParsedMetric] = field(default_factory=list)


def _iter_rows(
    *, fmt: str, data: bytes, max_rows: int,
) -> Iterable[tuple[int, dict]]:
    if fmt in ("csv", "tsv"):
        delim = "," if fmt == "csv" else "\t"
        text = data.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text), delimiter=delim)
        for i, row in enumerate(reader):
            if i >= max_rows:
                break
            yield i, dict(row)
        return
    if fmt == "json":
        obj = json.loads(data.decode("utf-8", errors="replace"))
        rows = obj if isinstance(obj, list) else [obj]
        for i, row in enumerate(rows):
            if i >= max_rows:
                break
            if isinstance(row, dict):
                yield i, row
        return
    if fmt in ("jsonl", "ndjson"):
        for i, line in enumerate(
            data.decode("utf-8", errors="replace").splitlines()
        ):
            if i >= max_rows:
                break
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield i, row


def parse_results_from_raw_artifact(
    *,
    project_file: ProjectFile,
    data: bytes,
    max_rows: int,
    max_metrics: int,
    context_hash: str,
) -> tuple[list[ParsedResult], list[str]]:
    warnings: list[str] = []
    fmt = _detect_format(project_file)
    if fmt is None:
        warnings.append("unsupported_result_format")
        return [], warnings

    rows = list(_iter_rows(fmt=fmt, data=data, max_rows=max_rows))
    if not rows:
        warnings.append("empty_result_artifact")
        return [], warnings

    column_names = list(rows[0][1].keys())
    metric_cols = [c for c in column_names if is_known_metric_name(c)]
    if not metric_cols:
        warnings.append("no_metric_columns")
        return [], warnings

    key_col = _pick(column_names, _EXPERIMENT_KEY_CANDIDATES)
    split_col = _pick_split(column_names)

    out: list[ParsedResult] = []
    metric_budget = max_metrics
    for idx, row in rows:
        prov_base = {
            "artifact_id": str(project_file.id),
            "file_name": (
                getattr(project_file, "original_filename", None)
                or getattr(project_file, "stored_filename", None)
            ),
            "format": fmt,
            "row": idx,
            "parser": f"m29_{fmt}",
            "parser_version": RESULT_PARSER_VERSION,
            "m29_version": M29_VERSION,
            "context_hash": context_hash,
        }
        exp_raw = row.get(key_col) if key_col else None
        exp_key = str(exp_raw) if exp_raw is not None else None
        split_val = (
            str(row.get(split_col))
            if split_col and row.get(split_col) is not None else None
        )

        metrics: list[ParsedMetric] = []
        for col in metric_cols:
            if metric_budget <= 0:
                break
            v = row.get(col)
            if v is None or v == "":
                continue
            num = _to_float(v)
            txt = None if num is not None else str(v)
            norm = normalize_metric_name(col)
            metrics.append(ParsedMetric(
                name=col, normalized_name=norm,
                value_numeric=num, value_text=txt,
                unit=None, split=split_val,
                direction=metric_direction(norm),
                provenance={**prov_base, "column": col},
            ))
            metric_budget -= 1
        if not metrics:
            continue

        name = (exp_key or f"result_row_{idx}")[:500]
        out.append(ParsedResult(
            result_type=ExperimentResultType.METRIC_OBSERVATION.value,
            name=name,
            experiment_key=exp_key[:500] if exp_key else None,
            value=dict(row),
            provenance={
                **prov_base, "experiment_key_column": key_col,
            },
            metrics=metrics,
        ))
    return out, warnings


__all__ = [
    "ParsedMetric", "ParsedResult", "parse_results_from_raw_artifact",
]
