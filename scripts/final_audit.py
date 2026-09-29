#!/usr/bin/env python3
"""Cross-platform final repository readiness audit."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    ".github/workflows/ci.yml",
    ".github/workflows/production-smoke.yml",
    ".github/workflows/chaos-recovery.yml",
    ".github/workflows/provider-activation.yml",
    "scripts/production_smoke.py",
    "scripts/chaos_recovery.py",
    "scripts/provider_activation.py",
    "scripts/backup_postgres.sh",
    "scripts/restore_postgres.sh",
    "scripts/frontend_security_audit.py",
)

SECRET_PATTERNS = (
    "-----BEGIN PRIVATE KEY-----",
    "sk-live-",
    "rk_live_",
    "whsec_",
)


def check_required() -> list[str]:
    return [path for path in REQUIRED if not (ROOT / path).is_file()]


def tracked_forbidden_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    forbidden: list[str] = []
    for raw in result.stdout.splitlines():
        path = raw.replace("\\", "/")
        name = Path(path).name
        if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
            forbidden.append(path)
    return forbidden


def secret_findings() -> list[str]:
    findings: list[str] = []
    for pattern in SECRET_PATTERNS:
        result = subprocess.run(
            ["git", "grep", "-n", "-I", "-e", pattern, "--", ":!*.md", ":!.env.example"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            findings.extend(result.stdout.splitlines())
    return findings


def main() -> int:
    missing = check_required()
    forbidden = tracked_forbidden_files()
    secrets = secret_findings()

    if missing:
        print("FAIL missing required artifacts:")
        for item in missing:
            print(f"  - {item}")
    if forbidden:
        print("FAIL tracked environment files:")
        for item in forbidden:
            print(f"  - {item}")
    if secrets:
        print("FAIL potential credential material:")
        for item in secrets:
            print(f"  - {item}")

    if missing or forbidden or secrets:
        print("Final audit: FAIL")
        return 1

    audit = subprocess.run(
        [sys.executable, "scripts/frontend_security_audit.py"],
        cwd=ROOT,
        check=False,
    )
    if audit.returncode != 0:
        print("Final audit: FAIL (frontend security audit)")
        return audit.returncode

    print("Final audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
