"""M20 — Data Intelligence domain (pure)."""
from __future__ import annotations

import re
from datetime import date, datetime
from enum import StrEnum


class DataFormat(StrEnum):
    CSV = "csv"
    TSV = "tsv"
    JSON = "json"
    JSONL = "jsonl"
    XLSX = "xlsx"
    UNKNOWN = "unknown"


class ColumnType(StrEnum):
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    STRING = "string"
    DATETIME = "datetime"
    DATE = "date"
    CATEGORY = "category"
    NULL = "null"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ProfileStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


ALL_DATA_FORMATS: tuple[str, ...] = tuple(f.value for f in DataFormat)
ALL_COLUMN_TYPES: tuple[str, ...] = tuple(t.value for t in ColumnType)
ALL_PROFILE_STATUSES: tuple[str, ...] = tuple(
    s.value for s in ProfileStatus
)

_EXT_TO_FORMAT: dict[str, DataFormat] = {
    ".csv": DataFormat.CSV,
    ".tsv": DataFormat.TSV,
    ".json": DataFormat.JSON,
    ".jsonl": DataFormat.JSONL,
    ".ndjson": DataFormat.JSONL,
    ".xlsx": DataFormat.XLSX,
}

_MIME_TO_FORMAT: dict[str, DataFormat] = {
    "text/csv": DataFormat.CSV,
    "text/tab-separated-values": DataFormat.TSV,
    "application/json": DataFormat.JSON,
    "application/x-ndjson": DataFormat.JSONL,
    "application/vnd.openxmlformats-officedocument"
    ".spreadsheetml.sheet": DataFormat.XLSX,
}


def detect_data_format(
    *, extension: str | None, mime: str | None
) -> DataFormat:
    if mime:
        base = mime.split(";", 1)[0].strip().lower()
        if base in _MIME_TO_FORMAT:
            return _MIME_TO_FORMAT[base]
    if extension:
        ext = extension.lower()
        if not ext.startswith("."):
            ext = "." + ext
        if ext in _EXT_TO_FORMAT:
            return _EXT_TO_FORMAT[ext]
    return DataFormat.UNKNOWN


_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$")


def infer_scalar_type(value: object) -> ColumnType:
    if value is None:
        return ColumnType.NULL
    if isinstance(value, bool):
        return ColumnType.BOOLEAN
    if isinstance(value, int):
        return ColumnType.INTEGER
    if isinstance(value, float):
        return ColumnType.FLOAT
    if isinstance(value, datetime):
        return ColumnType.DATETIME
    if isinstance(value, date):
        return ColumnType.DATE
    s = str(value).strip()
    if not s:
        return ColumnType.NULL
    low = s.lower()
    if low in ("true", "false", "yes", "no"):
        return ColumnType.BOOLEAN
    if _INT_RE.match(s):
        return ColumnType.INTEGER
    if _FLOAT_RE.match(s):
        return ColumnType.FLOAT
    try:
        if "T" in s or " " in s:
            datetime.fromisoformat(s.replace("Z", "+00:00"))
            return ColumnType.DATETIME
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            date.fromisoformat(s)
            return ColumnType.DATE
    except ValueError:
        pass
    return ColumnType.STRING


def aggregate_column_type(type_counts: dict[str, int]) -> ColumnType:
    observed = {t for t, n in type_counts.items() if n > 0}
    observed.discard(ColumnType.NULL.value)
    if not observed:
        return ColumnType.NULL
    if observed == {ColumnType.INTEGER.value}:
        return ColumnType.INTEGER
    if observed <= {ColumnType.INTEGER.value, ColumnType.FLOAT.value}:
        return ColumnType.FLOAT
    if observed == {ColumnType.BOOLEAN.value}:
        return ColumnType.BOOLEAN
    if observed == {ColumnType.DATETIME.value}:
        return ColumnType.DATETIME
    if observed == {ColumnType.DATE.value}:
        return ColumnType.DATE
    if observed == {ColumnType.STRING.value}:
        return ColumnType.STRING
    return ColumnType.MIXED


class DataIntelligenceError(Exception): ...
class DataMalformedError(DataIntelligenceError): ...
class DataResourceLimitError(DataIntelligenceError): ...
class DataUnsupportedFormatError(DataIntelligenceError): ...


class CodeIntelligenceError(Exception): ...
class CodeUnsupportedLanguageError(CodeIntelligenceError): ...
class CodeParseError(CodeIntelligenceError): ...
class CodeResourceLimitError(CodeIntelligenceError): ...
