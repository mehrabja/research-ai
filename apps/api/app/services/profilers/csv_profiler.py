"""M20 — CSV / TSV profiler (bounded memory)."""
from __future__ import annotations

import csv
import io
from collections.abc import Iterable

from app.core.config import get_settings
from app.services.profilers import ColumnStats, DataProfileResult
from app.services.profilers._accumulator import ColumnAccumulator


def _empty(fmt: str, error: str | None = None) -> DataProfileResult:
    return DataProfileResult(
        format=fmt,
        row_count=0,
        column_count=0,
        schema_data={},
        quality={},
        statistics={},
        sample_rows=[],
        columns=[],
        error=error,
    )


def profile_delimited(
    *, chunks: Iterable[bytes], delimiter: str
) -> DataProfileResult:
    settings = get_settings()
    fmt = "csv" if delimiter == "," else "tsv"

    buf = bytearray()
    for raw in chunks:
        buf.extend(raw)
    if not buf:
        return _empty(fmt)

    text = buf.decode("utf-8", errors="replace")

    try:
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        header = next(reader)
    except (csv.Error, StopIteration) as exc:
        return _empty(fmt, error=f"csv_parse_error: {exc}")

    col_count = len(header)
    if col_count == 0:
        return _empty(fmt)
    col_count = min(col_count, settings.data_profile_max_columns)
    header = header[:col_count]

    accumulators = [
        ColumnAccumulator(
            name=(h or f"col_{i}"),
            ordinal=i,
            distinct_cap=settings.data_profile_distinct_tracking_cap,
            top_values_limit=settings.data_profile_top_values_limit,
        )
        for i, h in enumerate(header)
    ]
    samples: list[dict] = []
    row_count = 0
    duplicate_set: set[tuple] = set()
    duplicate_count = 0
    scan_cap = settings.data_profile_max_rows_scanned
    scan_truncated = False

    try:
        for row in reader:
            if row_count >= scan_cap:
                scan_truncated = True
                break
            row_count += 1
            row = row[:col_count]
            if len(row) < col_count:
                row = row + [""] * (col_count - len(row))
            key = tuple(row)
            if key in duplicate_set:
                duplicate_count += 1
            else:
                duplicate_set.add(key)
                if (
                    len(duplicate_set)
                    > settings.data_profile_distinct_tracking_cap
                ):
                    duplicate_set.clear()
            for acc, value in zip(accumulators, row, strict=False):
                acc.add(value)
            if len(samples) < settings.data_profile_sample_rows:
                samples.append(dict(zip(header, row, strict=False)))
    except csv.Error as exc:
        return _empty(fmt, error=f"csv_parse_error: {exc}")

    cols: list[ColumnStats] = [a.finalize() for a in accumulators]

    schema_data = {
        "columns": [
            {"name": c.name, "ordinal": c.ordinal, "type": c.inferred_type}
            for c in cols
        ],
        "column_count": col_count,
    }
    quality = {
        "duplicate_row_count": duplicate_count,
        "duplicate_row_ratio": (
            duplicate_count / row_count if row_count else 0.0
        ),
        "null_heavy_columns": [
            c.name for c in cols
            if c.total_count and (c.null_count / c.total_count) >= 0.5
        ],
        "all_null_columns": [
            c.name for c in cols
            if c.null_count == c.total_count and c.total_count > 0
        ],
        "rows_scanned": row_count,
        "scan_truncated": scan_truncated,
    }
    statistics_summary = {
        "numeric_columns": [
            c.name for c in cols
            if c.inferred_type in ("integer", "float")
        ],
        "categorical_columns": [
            c.name for c in cols if c.inferred_type == "category"
        ],
    }

    return DataProfileResult(
        format=fmt,
        row_count=row_count,
        column_count=col_count,
        schema_data=schema_data,
        quality=quality,
        statistics=statistics_summary,
        sample_rows=samples,
        columns=cols,
        scan_truncated=scan_truncated,
    )
