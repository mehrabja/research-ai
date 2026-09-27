#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL is required}"
DUMP_FILE="${1:?Usage: restore_postgres.sh <dump-file>}"
CONFIRM="${CONFIRM_RESTORE:-}"

if [[ "$CONFIRM" != "yes" ]]; then
  echo "Set CONFIRM_RESTORE=yes to execute a destructive restore."
  exit 2
fi

pg_restore "$DUMP_FILE" \
  --dbname="$DATABASE_URL" \
  --clean --if-exists --no-owner --no-acl

echo "Restore completed from $DUMP_FILE"
