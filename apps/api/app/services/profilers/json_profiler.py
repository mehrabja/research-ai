"""M20 — JSON / JSONL profilers."""
from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from app.core.config import get_settings
from app.services.profilers import DataProfileResult
from app.services.profilers._accumulator import ColumnAccumulator


def _depth_ok(obj: Any, *, max_depth: int, _cur: int = 0) -> bool:
    if _cur > max_depth:
        return False
    if isinstance(obj, dict):
        return all(
            _depth_ok(v, max_depth=max_depth, _cur=_cur + 1)
            for v in obj.values()
        )
    if isinstance(obj, list):
        return all(
            _depth_ok(v, max_depth=max_depth, _cur=_cur + 1) for v in obj
        )
    return True


def _rows_from_json(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, list):
        return [r for r in obj if isinstance(r, dict)]
    if isinstance(obj, dict):
        for v in obj.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return [r for r in v if isinstance(r, dict)]
        return [obj]
    return []


def _profile_rows(
    rows: list[dict[str, Any]], *, fmt: str, scan_truncated: bool = False
) -> DataProfileResult:
    settings = get_settings()
    if not rows:
        return DataProfileResult(
            format=fmt,
            row_count=0,
            column_count=0,
            schema_data={},
            quality={"rows_scanned": 0, "scan_truncated": False},
            statistics={},
            sample_rows=[],
            columns=[],
        )
    keys: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k)
                keys.append(k)
            if len(keys) >= settings.data_profile_max_columns:
                break
        if len(keys) >= settings.data_profile_max_columns:
            break
    keys = keys[: settings.data_profile_max_columns]

    accs = [
        ColumnAccumulator(
            name=k,
            ordinal=i,
            distinct_cap=settings.data_profile_distinct_tracking_cap,
            top_values_limit=settings.data_profile_top_values_limit,
        )
        for i, k in enumerate(keys)
    ]
    for r in rows:
        for acc in accs:
            acc.add(r.get(acc.name))
    cols = [a.finalize() for a in accs]

    schema_data = {
        "columns": [
            {"name": c.name, "ordinal": c.ordinal, "type": c.inferred_type}
            for c in cols
        ],
        "column_count": len(cols),
    }
    quality = {
        "all_null_columns": [
            c.name for c in cols
            if c.null_count == c.total_count and c.total_count > 0
        ],
        "rows_scanned": len(rows),
        "scan_truncated": scan_truncated,
    }
    samples = rows[: settings.data_profile_sample_rows]
    return DataProfileResult(
        format=fmt,
        row_count=len(rows),
        column_count=len(cols),
        schema_data=schema_data,
        quality=quality,
        statistics={},
        sample_rows=samples,
        columns=cols,
        scan_truncated=scan_truncated,
    )


def profile_json(*, chunks: Iterable[bytes]) -> DataProfileResult:
    settings = get_settings()
    buf = bytearray()
    for raw in chunks:
        buf.extend(raw)
        if len(buf) > settings.data_json_max_bytes:
            return DataProfileResult(
                format="json",
                row_count=0,
                column_count=0,
                schema_data={},
                quality={},
                statistics={},
                sample_rows=[],
                columns=[],
                error="json_too_large",
            )
    try:
        obj = json.loads(buf.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return DataProfileResult(
            format="json",
            row_count=0,
            column_count=0,
            schema_data={},
            quality={},
            statistics={},
            sample_rows=[],
            columns=[],
            error=f"json_parse_error: {exc}",
        )
    if not _depth_ok(obj, max_depth=settings.data_json_max_depth):
        return DataProfileResult(
            format="json",
            row_count=0,
            column_count=0,
            schema_data={},
            quality={},
            statistics={},
            sample_rows=[],
            columns=[],
            error="json_too_deep",
        )
    rows = _rows_from_json(obj)
    scan_cap = settings.data_profile_max_rows_scanned
    scan_truncated = len(rows) > scan_cap
    if scan_truncated:
        rows = rows[:scan_cap]
    return _profile_rows(rows, fmt="json", scan_truncated=scan_truncated)


def profile_jsonl(*, chunks: Iterable[bytes]) -> DataProfileResult:
    settings = get_settings()
    rows: list[dict[str, Any]] = []
    buf = bytearray()
    for raw in chunks:
        buf.extend(raw)
    scan_cap = settings.data_profile_max_rows_scanned
    scan_truncated = False
    for line in bytes(buf).splitlines():
        if len(rows) >= scan_cap:
            scan_truncated = True
            break
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s.decode("utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return _profile_rows(
        rows, fmt="jsonl", scan_truncated=scan_truncated
    )
