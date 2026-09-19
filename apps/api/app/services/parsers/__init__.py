"""M20 — Code parsers dispatcher."""
from __future__ import annotations

from app.domain.code_intelligence import (
    Language,
    LanguageSupport,
    language_support,
)
from app.services.parsers.base import (
    CodeParseResult,
    RawDependency,
    RawSymbol,
)
from app.services.parsers.fallback_parser import parse_fallback
from app.services.parsers.python_parser import parse_python

__all__ = [
    "CodeParseResult",
    "RawDependency",
    "RawSymbol",
    "parse_source",
]


def parse_source(
    *, source: str, language: Language
) -> CodeParseResult:
    support = language_support(language)
    if support is LanguageSupport.UNSUPPORTED:
        return CodeParseResult(
            parser="none",
            parser_version="0",
            supported=False,
            symbols=(),
            dependencies=(),
            line_count=source.count("\n")
            + (0 if source.endswith("\n") else 1),
            character_count=len(source),
            module_docstring=None,
            error=None,
        )
    if language is Language.PYTHON:
        return parse_python(source)
    return parse_fallback(source=source, language=language)
