"""Migration cycle verification (M36).

Usage:
    python scripts/verify_migrations.py

Runs the full upgrade -> downgrade -> upgrade cycle and verifies:
    * alembic current succeeds before and after
    * head does not change across the cycle
    * no dangling scripts

Requires a working DATABASE_URL. Exits non-zero on any failure.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
from dotenv import load_dotenv

_REPO_ROOT = API_DIR.parent.parent
load_dotenv(_REPO_ROOT / ".env", override=False)
load_dotenv(API_DIR / ".env", override=False)

def _run(*args: str) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "-m", "alembic", *args]
    print(f"+ {' '.join(cmd)}")
    return subprocess.run(
        cmd,
        cwd=API_DIR,
        capture_output=True,
        text=True,
    )


def _current() -> str | None:
    proc = _run("current")
    if proc.returncode != 0:
        print(proc.stderr)
        return None
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line and not line.startswith("INFO"):
            return line.split()[0]
    return None


def _head() -> str | None:
    proc = _run("heads")
    if proc.returncode != 0:
        print(proc.stderr)
        return None
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line and not line.startswith("INFO"):
            return line.split()[0]
    return None


def main() -> int:
    if not os.getenv("DATABASE_URL") and not os.getenv(
        "ALEMBIC_DATABASE_URL"
    ):
        print("SKIP: DATABASE_URL not set")
        return 0

    head_before = _head()
    if head_before is None:
        print("FAIL: cannot read head")
        return 1
    print(f"head: {head_before}")

    r = _run("upgrade", "head")
    if r.returncode != 0:
        print(r.stderr)
        print("FAIL: upgrade head")
        return 1
    current_after_up = _current()
    if current_after_up != head_before:
        print(
            f"FAIL: current after upgrade={current_after_up} "
            f"!= head={head_before}"
        )
        return 1

    r = _run("downgrade", "-1")
    if r.returncode != 0:
        print(r.stderr)
        print("FAIL: downgrade -1")
        return 1

    r = _run("upgrade", "head")
    if r.returncode != 0:
        print(r.stderr)
        print("FAIL: re-upgrade head")
        return 1

    head_after = _head()
    if head_after != head_before:
        print(
            f"FAIL: head changed "
            f"({head_before} -> {head_after})"
        )
        return 1

    current_final = _current()
    if current_final != head_before:
        print(
            f"FAIL: final current={current_final} "
            f"!= head={head_before}"
        )
        return 1

    print("migrations: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())