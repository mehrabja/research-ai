#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../apps/api"

alembic heads
HEAD_COUNT="$(alembic heads | grep -cE '^[0-9a-z]+ \\(' || true)"
if [[ "$HEAD_COUNT" -ne 1 ]]; then
  echo "Expected exactly one Alembic head; found ${HEAD_COUNT}."
  exit 1
fi

alembic check
