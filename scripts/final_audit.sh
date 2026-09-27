#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== migration graph =="
bash scripts/check_migrations.sh

echo "== API checks =="
make api-lint
make api-typecheck

echo "== Frontend checks =="
make web-typecheck
make web-build
make web-test

echo "== repository hygiene =="
if git grep -nE '(BEGIN (PRIVATE|SECRET)|sk-[A-Za-z0-9]{20,}|rk_live_|whsec_)' -- ':!*.md' ':!.env.example'; then
  echo "Potential credential material detected."
  exit 1
fi

echo "Final audit script completed. Runtime smoke/recovery evidence still belongs to the deployment environment."
