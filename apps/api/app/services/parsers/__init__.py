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
from app.services.parsers.notebook_parser import parse_notebook

__all__ = [
    "CodeParseResult",
    "RawDependency",
    "RawSymbol",
    "parse_source",
]


def parse_source(
    *,
    source: str,
    language: Language,
    notebook_max_cells: int = 2000,
    notebook_max_cell_source_chars: int = 250_000,
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
    if language is Language.NOTEBOOK:
        return parse_notebook(
            source,
            max_cells=notebook_max_cells,
            max_cell_source_chars=notebook_max_cell_source_chars,
        )
    return parse_fallback(source=source, language=language)
