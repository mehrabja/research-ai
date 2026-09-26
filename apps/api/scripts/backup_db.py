"""Database backup CLI (M36).

Usage:
    python scripts/backup_db.py [--output PATH] [--format custom|plain]
                                [--no-retention]

Environment:
    DATABASE_URL             (required; from .env or shell)
    BACKUP_DIRECTORY         (optional; default 'backups')
    BACKUP_RETENTION_DAYS    (optional; default 14)

Behaviour:
    * Refuses to run when DATABASE_URL looks like a test database
      unless --allow-test is passed.
    * Uses pg_dump on PATH.
    * Writes <name>.<ext> plus <name>.meta.json (sha256, size,
      duration, alembic head, format, dump tool version).
    * Applies retention on .dump/.sql files older than retention days
      unless --no-retention is given.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(REPO_ROOT / ".env", override=False)


def _require_pg_dump() -> str:
    path = shutil.which("pg_dump")
    if not path:
        print(
            "ERROR: pg_dump not found on PATH. "
            "Install PostgreSQL client tools.",
            file=sys.stderr,
        )
        sys.exit(2)
    return path


def _is_test_url(url: str) -> bool:
    low = url.lower()
    return (
        "test" in low
        or "localhost" in low
        or "127.0.0.1" in low
    )


def _sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            data = fh.read(chunk)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def _pg_dump_version(pg_dump: str) -> str:
    try:
        out = subprocess.run(
            [pg_dump, "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except subprocess.CalledProcessError:
        return "unknown"


def _alembic_head(api_dir: Path) -> str | None:
    try:
        out = subprocess.run(
            [
                sys.executable,
                "-m",
                "alembic",
                "heads",
            ],
            cwd=api_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        first = out.stdout.strip().splitlines()
        return first[0].split()[0] if first else None
    except Exception:
        return None


def _apply_retention(
    directory: Path, *, days: int
) -> list[Path]:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    removed: list[Path] = []
    for path in directory.iterdir():
        if not path.is_file():
            continue
        if path.suffix not in (".dump", ".sql"):
            continue
        mtime = datetime.fromtimestamp(
            path.stat().st_mtime, tz=UTC
        )
        if mtime < cutoff:
            path.unlink()
            meta = path.with_suffix(path.suffix + ".meta.json")
            meta.unlink(missing_ok=True)
            removed.append(path)
    return removed


def main() -> int:
    _load_env()

    parser = argparse.ArgumentParser(
        description="Create a PostgreSQL backup."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Target file path (default: auto-named in BACKUP_DIRECTORY).",
    )
    parser.add_argument(
        "--format",
        choices=("custom", "plain"),
        default="custom",
    )
    parser.add_argument(
        "--directory",
        type=Path,
        default=None,
        help="Backup directory (overrides BACKUP_DIRECTORY).",
    )
    parser.add_argument(
        "--allow-test",
        action="store_true",
        help="Allow backup of a test/local database.",
    )
    parser.add_argument(
        "--no-retention",
        action="store_true",
    )
    args = parser.parse_args()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL is not set", file=sys.stderr)
        return 2

    if not args.allow_test and _is_test_url(db_url):
        print(
            "ERROR: DATABASE_URL looks like a test/local database. "
            "Pass --allow-test to override.",
            file=sys.stderr,
        )
        return 2

    pg_dump = _require_pg_dump()

    api_dir = Path(__file__).resolve().parents[1]
    directory = (
        args.directory
        or Path(
            os.getenv(
                "BACKUP_DIRECTORY",
                "backups",
            )
        )
    )
    if not directory.is_absolute():
        directory = api_dir / directory
    directory.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    ext = ".dump" if args.format == "custom" else ".sql"
    target = args.output or (
        directory / f"research-ai-{timestamp}{ext}"
    )
    target.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        pg_dump,
        "--no-owner",
        "--no-privileges",
    ]
    if args.format == "custom":
        cmd.append("--format=custom")
    else:
        cmd.append("--format=plain")
    cmd += ["--file", str(target), db_url]

    started = time.monotonic()
    print(f"backup: running {pg_dump} -> {target}")
    try:
        proc = subprocess.run(cmd, check=False)
    except FileNotFoundError:
        print("ERROR: pg_dump disappeared", file=sys.stderr)
        return 2
    duration = time.monotonic() - started

    if proc.returncode != 0:
        target.unlink(missing_ok=True)
        print(
            f"ERROR: pg_dump failed with code {proc.returncode}",
            file=sys.stderr,
        )
        return 1

    sha = _sha256_file(target)
    size = target.stat().st_size
    meta = {
        "created_at": datetime.now(UTC).isoformat(),
        "source_file": target.name,
        "format": args.format,
        "sha256": sha,
        "size_bytes": size,
        "duration_seconds": round(duration, 3),
        "pg_dump_version": _pg_dump_version(pg_dump),
        "alembic_head_at_backup": _alembic_head(api_dir),
    }
    meta_path = target.with_suffix(target.suffix + ".meta.json")
    meta_path.write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )

    print(
        f"backup: wrote {target.name} "
        f"({size} bytes, sha256={sha[:12]}...)"
    )
    print(f"backup: metadata at {meta_path.name}")

    if not args.no_retention:
        days = int(os.getenv("BACKUP_RETENTION_DAYS", "14"))
        removed = _apply_retention(directory, days=days)
        if removed:
            print(
                f"backup: retention removed {len(removed)} old "
                f"file(s) older than {days} days"
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())