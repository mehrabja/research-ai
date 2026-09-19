"""M20 — Regex-based fallback parser for non-Python languages."""
from __future__ import annotations

import re

from app.domain.code_intelligence import Language
from app.services.parsers.base import (
    CodeParseResult,
    RawDependency,
    RawSymbol,
)

PARSER_NAME = "regex"
PARSER_VERSION = "m20.1"

_JS_IMPORT = re.compile(
    r"^\s*import\s+(?:[^'\"]+?\s+from\s+)?['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)
_JS_REQUIRE = re.compile(
    r"require\(\s*['\"]([^'\"]+)['\"]\s*\)"
)
_JS_FUNC = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)",
    re.MULTILINE,
)
_JS_CLASS = re.compile(
    r"^\s*(?:export\s+)?class\s+(\w+)",
    re.MULTILINE,
)
_SQL_STMT = re.compile(
    r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)\b",
    re.IGNORECASE,
)
_SQL_TABLE = re.compile(
    r"\b(?:FROM|INTO|UPDATE|JOIN)\s+([A-Za-z_][\w\.]*)",
    re.IGNORECASE,
)
_SQL_WITH = re.compile(r"\bWITH\s+(\w+)\s+AS\b", re.IGNORECASE)

_SH_FUNC = re.compile(
    r"^\s*(?:function\s+)?(\w+)\s*\(\s*\)\s*\{", re.MULTILINE
)


def parse_fallback(*, source: str, language: Language) -> CodeParseResult:
    line_count = source.count("\n") + (0 if source.endswith("\n") else 1)
    char_count = len(source)
    symbols: list[RawSymbol] = []
    dependencies: list[RawDependency] = []

    if language in (Language.JAVASCRIPT, Language.TYPESCRIPT):
        for m in _JS_IMPORT.finditer(source):
            ln = source[: m.start()].count("\n") + 1
            name = m.group(1)
            dependencies.append(
                RawDependency(
                    dependency_name=name,
                    dependency_type="import",
                    line_number=ln,
                    is_relative=name.startswith("."),
                )
            )
        for m in _JS_REQUIRE.finditer(source):
            ln = source[: m.start()].count("\n") + 1
            name = m.group(1)
            dependencies.append(
                RawDependency(
                    dependency_name=name,
                    dependency_type="require",
                    line_number=ln,
                    is_relative=name.startswith("."),
                )
            )
        for m in _JS_FUNC.finditer(source):
            ln = source[: m.start()].count("\n") + 1
            symbols.append(
                RawSymbol(
                    symbol_type="function",
                    name=m.group(1),
                    qualified_name=m.group(1),
                    parent_name=None,
                    line_start=ln,
                    line_end=ln,
                    signature=f"function {m.group(1)}",
                )
            )
        for m in _JS_CLASS.finditer(source):
            ln = source[: m.start()].count("\n") + 1
            symbols.append(
                RawSymbol(
                    symbol_type="class",
                    name=m.group(1),
                    qualified_name=m.group(1),
                    parent_name=None,
                    line_start=ln,
                    line_end=ln,
                    signature=f"class {m.group(1)}",
                )
            )

    elif language is Language.SQL:
        for m in _SQL_STMT.finditer(source):
            ln = source[: m.start()].count("\n") + 1
            stmt = m.group(1).upper()
            symbols.append(
                RawSymbol(
                    symbol_type="function",
                    name=stmt,
                    qualified_name=stmt,
                    parent_name=None,
                    line_start=ln,
                    line_end=ln,
                    signature=stmt,
                    meta={"kind": "statement"},
                )
            )
        for m in _SQL_TABLE.finditer(source):
            name = m.group(1)
            dependencies.append(
                RawDependency(
                    dependency_name=name,
                    dependency_type="unknown",
                    line_number=None,
                    is_relative=False,
                    meta={"kind": "table"},
                )
            )
        for m in _SQL_WITH.finditer(source):
            ln = source[: m.start()].count("\n") + 1
            symbols.append(
                RawSymbol(
                    symbol_type="variable",
                    name=m.group(1),
                    qualified_name=m.group(1),
                    parent_name=None,
                    line_start=ln,
                    line_end=ln,
                    signature=f"CTE {m.group(1)}",
                    meta={"kind": "cte"},
                )
            )

    elif language is Language.SHELL:
        for m in _SH_FUNC.finditer(source):
            ln = source[: m.start()].count("\n") + 1
            symbols.append(
                RawSymbol(
                    symbol_type="function",
                    name=m.group(1),
                    qualified_name=m.group(1),
                    parent_name=None,
                    line_start=ln,
                    line_end=ln,
                    signature=f"{m.group(1)}()",
                )
            )

    return CodeParseResult(
        parser=PARSER_NAME,
        parser_version=PARSER_VERSION,
        supported=True,
        symbols=tuple(symbols),
        dependencies=tuple(dependencies),
        line_count=line_count,
        character_count=char_count,
        module_docstring=None,
        error=None,
        complexity_score=None,
    )
