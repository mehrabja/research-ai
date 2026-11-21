"""M20 — Intelligence schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

LanguageLiteral = Literal[
    "python", "notebook", "javascript", "typescript", "java", "c", "cpp", "go",
    "rust", "sql", "shell", "unknown",
]
ParseStatusLiteral = Literal[
    "pending", "completed", "failed", "unsupported"
]
SymbolTypeLiteral = Literal[
    "module", "class", "function", "method", "variable", "constant",
    "import",
]
DependencyTypeLiteral = Literal[
    "import", "from_import", "require", "include", "package", "unknown",
]
DataFormatLiteral = Literal["csv", "tsv", "json", "jsonl", "xlsx", "unknown"]
ColumnTypeLiteral = Literal[
    "integer", "float", "boolean", "string", "datetime", "date",
    "category", "null", "mixed", "unknown",
]
ProfileStatusLiteral = Literal[
    "pending", "completed", "failed", "unsupported"
]


class CodeAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    project_file_id: uuid.UUID
    language: LanguageLiteral
    parser: str
    parser_version: str
    analysis_version: str
    parse_status: ParseStatusLiteral
    parse_error: str | None
    line_count: int
    character_count: int
    symbol_count: int
    function_count: int
    class_count: int
    import_count: int
    complexity_score: float | None
    analysis_meta: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class CodeSymbolRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    symbol_type: SymbolTypeLiteral
    name: str
    qualified_name: str
    parent_name: str | None
    line_start: int
    line_end: int
    column_start: int | None
    column_end: int | None
    signature: str | None
    docstring: str | None


class CodeSymbolListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CodeSymbolRead]
    total: int
    limit: int
    offset: int


class CodeDependencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    dependency_name: str
    dependency_type: DependencyTypeLiteral
    line_number: int | None
    is_relative: bool


class CodeDependencyListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CodeDependencyRead]
    total: int
    limit: int
    offset: int


class DataProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    project_file_id: uuid.UUID
    format: DataFormatLiteral
    profile_status: ProfileStatusLiteral
    profile_error: str | None
    profile_version: str
    row_count: int | None
    column_count: int | None
    schema_data: dict | None
    quality: dict | None
    statistics: dict | None
    sample_rows: list[dict[str, Any]] | None
    created_at: datetime
    updated_at: datetime


class DataColumnProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    name: str
    ordinal: int
    inferred_type: ColumnTypeLiteral
    nullable: bool
    null_count: int
    null_ratio: float
    distinct_count: int | None
    unique_ratio: float | None
    min_value: str | None
    max_value: str | None
    mean: float | None
    median: float | None
    stddev: float | None
    top_values: list[dict[str, Any]] | None


class DataColumnListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DataColumnProfileRead]
    total: int
    limit: int
    offset: int
