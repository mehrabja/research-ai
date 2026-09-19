"""M20 — Data profilers dispatcher."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from app.domain.data_intelligence import DataFormat

__all__ = [
    "ColumnStats",
    "DataProfileResult",
    "profile_data",
]


@dataclass
class ColumnStats:
    name: str
    ordinal: int
    inferred_type: str
    nullable: bool
    null_count: int
    total_count: int
    distinct_count: int | None
    unique_ratio: float | None
    min_value: str | None = None
    max_value: str | None = None
    mean: float | None = None
    median: float | None = None
    stddev: float | None = None
    top_values: list[dict] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


@dataclass
class DataProfileResult:
    format: str
    row_count: int
    column_count: int
    schema_data: dict
    quality: dict
    statistics: dict
    sample_rows: list[dict]
    columns: list[ColumnStats]
    error: str | None = None
    scan_truncated: bool = False


def profile_data(
    *, chunks: Iterable[bytes], fmt: DataFormat
) -> DataProfileResult:
    from app.services.profilers.csv_profiler import profile_delimited
    from app.services.profilers.json_profiler import (
        profile_json,
        profile_jsonl,
    )
    from app.services.profilers.xlsx_profiler import profile_xlsx

    if fmt is DataFormat.CSV:
        return profile_delimited(chunks=chunks, delimiter=",")
    if fmt is DataFormat.TSV:
        return profile_delimited(chunks=chunks, delimiter="\t")
    if fmt is DataFormat.JSON:
        return profile_json(chunks=chunks)
    if fmt is DataFormat.JSONL:
        return profile_jsonl(chunks=chunks)
    if fmt is DataFormat.XLSX:
        return profile_xlsx(chunks=chunks)
    return DataProfileResult(
        format=fmt.value,
        row_count=0,
        column_count=0,
        schema_data={},
        quality={},
        statistics={},
        sample_rows=[],
        columns=[],
        error=f"unsupported format: {fmt.value}",
    )
