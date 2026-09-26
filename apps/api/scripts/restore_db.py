"""Database restore CLI (M36).

Usage:
    python scripts/restore_db.py BACKUP_FILE --target-url URL
        [--clean] [--dry-run] [--yes] [--force]

Safety:
    * Requires --yes when the target is not empty.
    * Refuses when the target URL equals DATABASE_URL unless --force.
    * --dry-run prints what would run and exits 0.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        print(
            f"ERROR: {name} not found on PATH. "
            "Install PostgreSQL client tools.",
            file=sys.stderr,
        )
        sys.exit(2)
    return path


def _looks_custom(path: Path) -> bool:
    return path.suffix.lower() in (".dump", ".backup")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Restore a PostgreSQL backup."
    )
    parser.add_argument("backup", type=Path)
    parser.add_argument(
        "--target-url",
        required=True,
        help="Target PostgreSQL URL.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Drop objects before restore (pg_restore --clean).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm destructive restore.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow target == DATABASE_URL.",
    )
    args = parser.parse_args()

    backup = args.backup
    if not backup.exists():
        print(
            f"ERROR: backup file not found: {backup}",
            file=sys.stderr,
        )
        return 2

    env_url = os.getenv("DATABASE_URL")
    if env_url and env_url == args.target_url and not args.force:
        print(
            "ERROR: target-url equals DATABASE_URL. "
            "Pass --force if this is intentional.",
            file=sys.stderr,
        )
        return 2

    is_custom = _looks_custom(backup)
    if is_custom:
        tool = _require_tool("pg_restore")
        cmd = [tool, "--no-owner", "--no-privileges"]
        if args.clean:
            cmd.append("--clean")
            cmd.append("--if-exists")
        cmd += ["--dbname", args.target_url, str(backup)]
    else:
        tool = _require_tool("psql")
        cmd = [tool, "--no-psqlrc", args.target_url, "-f", str(backup)]

    print("restore: would run:")
    print("  " + " ".join(cmd))

    if args.dry_run:
        print("restore: dry-run - exiting without executing.")
        return 0

    if not args.yes:
        print(
            "restore: refusing to run without --yes.",
            file=sys.stderr,
        )
        return 2

    proc = subprocess.run(cmd, check=False)
    if proc.returncode != 0:
        print(
            f"ERROR: restore failed with code {proc.returncode}",
            file=sys.stderr,
        )
        return 1

    print("restore: completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())