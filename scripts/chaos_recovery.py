#!/usr/bin/env python3
"""Repeatable Phase 18 failure/chaos/recovery verification."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
SUITES: dict[str, tuple[str, ...]] = {
    "failure": ("tests/failure",),
    "providers": ("tests/providers",),
    "storage": ("tests/storage",),
    "workers": ("tests/workers",),
    "all": ("tests/failure", "tests/providers", "tests/storage", "tests/workers"),
}


def run_suite(name: str, paths: tuple[str, ...]) -> None:
    command = [sys.executable, "-m", "pytest", "-q", *paths]
    print(f"== Phase 18 {name} ==")
    result = subprocess.run(command, cwd=API_DIR, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    print(f"PASS {name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=tuple(SUITES), default="all")
    args = parser.parse_args()
    print("Phase 18 chaos/recovery runner")
    print("No production fault injection is enabled by this command.")
    run_suite(args.suite, SUITES[args.suite])
    print("Phase 18 chaos/recovery: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
