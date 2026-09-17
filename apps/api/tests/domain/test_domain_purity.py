"""Static check: the domain package must not import from higher layers.

Dependency direction (mandatory):

    integrations ──► domain
    services     ──► domain
    db           ──► domain
    api          ──► domain

    domain ─────X──► integrations
    domain ─────X──► services
    domain ─────X──► db
    domain ─────X──► api

The repository uses absolute application imports; this check enforces
the forbidden absolute package dependencies. Relative imports are not
supported by this milestone's convention.
"""
from __future__ import annotations

import ast
from pathlib import Path

DOMAIN_DIR = Path(__file__).resolve().parents[2] / "app" / "domain"

FORBIDDEN_PREFIXES = (
    "app.integrations",
    "app.services",
    "app.db",
    "app.api",
)


def _iter_domain_files() -> list[Path]:
    return sorted(
        p for p in DOMAIN_DIR.rglob("*.py") if p.name != "__init__.py"
    )


def _iter_imports(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_domain_has_no_forbidden_imports() -> None:
    violations: list[str] = []
    files = _iter_domain_files()
    assert files, "no domain files found"

    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for name in _iter_imports(tree):
            if name.startswith(FORBIDDEN_PREFIXES):
                violations.append(f"{path.name}: imports {name}")

    assert not violations, (
        "domain purity violated:\n  " + "\n  ".join(violations)
    )


def test_domain_does_not_import_settings_or_httpx() -> None:
    forbidden = ("app.core.config", "httpx", "sqlalchemy", "fastapi")
    violations: list[str] = []
    for path in _iter_domain_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for name in _iter_imports(tree):
            if name.startswith(forbidden):
                violations.append(f"{path.name}: imports {name}")
    assert not violations, (
        "domain runtime-purity violated:\n  " + "\n  ".join(violations)
    )
