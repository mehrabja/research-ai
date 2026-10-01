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
    ".github/workflows/staging-deploy-smoke.yml",
    ".github/workflows/staging-chaos.yml",
    ".github/workflows/staging-backup-restore.yml",
    ".github/workflows/staging-release-evidence.yml",
    "scripts/production_smoke.py",
    "scripts/chaos_recovery.py",
    "scripts/provider_activation.py",
    "scripts/staging_deploy.ps1",
    "scripts/staging_run_smoke.ps1",
    "scripts/staging_chaos.ps1",
    "scripts/staging_backup_restore.ps1",
    "scripts/backup_postgres.sh",
    "scripts/restore_postgres.sh",
    "scripts/frontend_security_audit.py",
)

ENV_EXAMPLE_NAMES = {
    ".env.example",
    ".env.production.example",
    ".env.staging.example",
    ".env.test.example",
}

AUDIT_REFERENCE_FILES = {
    "scripts/final_audit.py",
    "scripts/final_audit.sh",
    "scripts/frontend_security_audit.py",
    "apps/api/app/core/logging.py",
    "apps/web/e2e/f15-security-observability.spec.ts",
}

SECRET_PATTERNS = (
    "-----BEGIN " + "PRIVATE KEY-----",
    "sk-live" + "-",
    "rk" + "_live_",
    "wh" + "sec_",
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
        if name == ".env" or (
            name.startswith(".env.")
            and name not in ENV_EXAMPLE_NAMES
        ):
            forbidden.append(path)
    return forbidden


def secret_findings() -> list[str]:
    findings: list[str] = []
    pathspecs = [
        ":!*.md",
        *[f":!{path}" for path in sorted(AUDIT_REFERENCE_FILES)],
        *[f":!{name}" for name in sorted(ENV_EXAMPLE_NAMES)],
    ]
    for pattern in SECRET_PATTERNS:
        result = subprocess.run(
            ["git", "grep", "-n", "-I", "-e", pattern, "--", *pathspecs],
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
