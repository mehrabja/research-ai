"""Verify a backup file (M36).

Usage:
    python scripts/verify_backup.py BACKUP_FILE

Checks:
    * sidecar .meta.json present and parseable
    * sha256 matches sidecar
    * size matches sidecar
    * pg_restore --list succeeds for custom dumps
    * alembic version marker present (best-effort)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            data = fh.read(chunk)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def _looks_custom(path: Path) -> bool:
    return path.suffix.lower() in (".dump", ".backup")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify a backup file and its sidecar metadata."
    )
    parser.add_argument("backup", type=Path)
    args = parser.parse_args()

    backup = args.backup
    if not backup.exists():
        print(f"FAIL: backup not found: {backup}")
        return 2

    meta_path = backup.with_suffix(backup.suffix + ".meta.json")
    if not meta_path.exists():
        print(f"FAIL: metadata not found: {meta_path.name}")
        return 1

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print("FAIL: metadata is not valid JSON")
        return 1

    actual_size = backup.stat().st_size
    if meta.get("size_bytes") != actual_size:
        print(
            f"FAIL: size mismatch "
            f"(meta={meta.get('size_bytes')} actual={actual_size})"
        )
        return 1

    actual_sha = _sha256_file(backup)
    if meta.get("sha256") != actual_sha:
        print("FAIL: sha256 mismatch")
        return 1

    print(f"OK: size={actual_size} sha256={actual_sha[:12]}...")

    if _looks_custom(backup):
        pg_restore = shutil.which("pg_restore")
        if not pg_restore:
            print(
                "WARN: pg_restore not on PATH; "
                "skipping structural verification"
            )
            return 0
        proc = subprocess.run(
            [pg_restore, "--list", str(backup)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            print("FAIL: pg_restore --list failed")
            print(proc.stderr)
            return 1
        toc = proc.stdout
        if "alembic_version" not in toc.lower():
            print("WARN: alembic_version table not seen in TOC")
        else:
            print("OK: alembic_version table present in TOC")

    print("verify: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())