"""M20 — Shared parser dataclasses."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RawSymbol:
    symbol_type: str
    name: str
    qualified_name: str
    parent_name: str | None
    line_start: int
    line_end: int
    column_start: int | None = None
    column_end: int | None = None
    signature: str | None = None
    docstring: str | None = None
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RawDependency:
    dependency_name: str
    dependency_type: str
    line_number: int | None
    is_relative: bool
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class CodeParseResult:
    parser: str
    parser_version: str
    supported: bool
    symbols: tuple[RawSymbol, ...]
    dependencies: tuple[RawDependency, ...]
    line_count: int
    character_count: int
    module_docstring: str | None
    error: str | None
    complexity_score: float | None = None
    analysis_meta: dict = field(default_factory=dict)
