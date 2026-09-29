#!/usr/bin/env python3
"""Static frontend security audit for high-risk browser sinks and secrets."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "apps" / "web"
SKIP_PARTS = {"node_modules", ".next", "playwright-report", "test-results", "e2e"}

PATTERNS = {
    "dangerouslySetInnerHTML": re.compile(r"\bdangerouslySetInnerHTML\b"),
    "eval": re.compile(r"\beval\s*\("),
    "new Function": re.compile(r"\bnew\s+Function\s*\("),
    "document.write": re.compile(r"\bdocument\.write\s*\("),
    "innerHTML assignment": re.compile(r"\binnerHTML\s*="),
    "private key material": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
    "provider secret pattern": re.compile(
        r"\b(?:sk-or-v1-|sk-|whsec_)\S{12,}"
    ),
}

EXTENSIONS = {".ts", ".tsx", ".js", ".jsx"}


def iter_source_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in EXTENSIONS:
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        yield path


def main() -> int:
    findings: list[str] = []

    for path in iter_source_files():
        source = path.read_text(encoding="utf-8", errors="ignore")
        for name, pattern in PATTERNS.items():
            for match in pattern.finditer(source):
                line = source.count("\n", 0, match.start()) + 1
                findings.append(f"{path.relative_to(ROOT)}:{line}: {name}")

    if findings:
        print("Frontend security audit failed:")
        for finding in findings:
            print(f"  - {finding}")
        return 1

    print("Frontend security audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
