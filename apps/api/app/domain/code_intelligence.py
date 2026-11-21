"""M20 — Code Intelligence domain (pure)."""
from __future__ import annotations

from enum import StrEnum


class Language(StrEnum):
    PYTHON = "python"
    NOTEBOOK = "notebook"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    C = "c"
    CPP = "cpp"
    GO = "go"
    RUST = "rust"
    SQL = "sql"
    SHELL = "shell"
    UNKNOWN = "unknown"


class LanguageSupport(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    FALLBACK = "fallback"
    UNSUPPORTED = "unsupported"


class ParseStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


class SymbolType(StrEnum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    CONSTANT = "constant"
    IMPORT = "import"


class DependencyType(StrEnum):
    IMPORT = "import"
    FROM_IMPORT = "from_import"
    REQUIRE = "require"
    INCLUDE = "include"
    PACKAGE = "package"
    UNKNOWN = "unknown"


ALL_LANGUAGES: tuple[str, ...] = tuple(lang.value for lang in Language)
ALL_PARSE_STATUSES: tuple[str, ...] = tuple(s.value for s in ParseStatus)
ALL_SYMBOL_TYPES: tuple[str, ...] = tuple(s.value for s in SymbolType)
ALL_DEPENDENCY_TYPES: tuple[str, ...] = tuple(
    d.value for d in DependencyType
)

_EXT_TO_LANG: dict[str, Language] = {
    ".py": Language.PYTHON,
    ".pyi": Language.PYTHON,
    ".ipynb": Language.NOTEBOOK,
    ".js": Language.JAVASCRIPT,
    ".mjs": Language.JAVASCRIPT,
    ".cjs": Language.JAVASCRIPT,
    ".jsx": Language.JAVASCRIPT,
    ".ts": Language.TYPESCRIPT,
    ".tsx": Language.TYPESCRIPT,
    ".java": Language.JAVA,
    ".c": Language.C,
    ".h": Language.C,
    ".cpp": Language.CPP,
    ".cc": Language.CPP,
    ".cxx": Language.CPP,
    ".hpp": Language.CPP,
    ".hh": Language.CPP,
    ".go": Language.GO,
    ".rs": Language.RUST,
    ".sql": Language.SQL,
    ".sh": Language.SHELL,
    ".bash": Language.SHELL,
    ".zsh": Language.SHELL,
}

_SUPPORT: dict[Language, LanguageSupport] = {
    Language.PYTHON: LanguageSupport.FULL,
    Language.NOTEBOOK: LanguageSupport.FULL,
    Language.JAVASCRIPT: LanguageSupport.FALLBACK,
    Language.TYPESCRIPT: LanguageSupport.FALLBACK,
    Language.SQL: LanguageSupport.FALLBACK,
    Language.SHELL: LanguageSupport.FALLBACK,
    # No real parser yet — mark UNSUPPORTED so status is recorded
    # accurately (not silently-empty "completed").
    Language.JAVA: LanguageSupport.UNSUPPORTED,
    Language.C: LanguageSupport.UNSUPPORTED,
    Language.CPP: LanguageSupport.UNSUPPORTED,
    Language.GO: LanguageSupport.UNSUPPORTED,
    Language.RUST: LanguageSupport.UNSUPPORTED,
    Language.UNKNOWN: LanguageSupport.UNSUPPORTED,
}


def detect_language(extension: str | None) -> Language:
    if not extension:
        return Language.UNKNOWN
    ext = extension.lower()
    if not ext.startswith("."):
        ext = "." + ext
    return _EXT_TO_LANG.get(ext, Language.UNKNOWN)


def language_support(lang: Language) -> LanguageSupport:
    return _SUPPORT.get(lang, LanguageSupport.UNSUPPORTED)
