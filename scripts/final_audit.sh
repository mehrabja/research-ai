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
if git grep -nE '(BEGIN (PRIVATE|SECRET)|sk-[A-Za-z0-9]{20,}|rk_live_|whsec_)' \
  -- ':!*.md' \
     ':!**/.env.example' \
     ':!apps/api/.env.production.example' \
     ':!apps/api/.env.staging.example' \
     ':!apps/api/.env.test.example' \
     ':!scripts/final_audit.py' \
     ':!scripts/final_audit.sh' \
     ':!scripts/frontend_security_audit.py' \
     ':!apps/api/app/core/logging.py' \
     ':!apps/web/e2e/f15-security-observability.spec.ts'; then
  echo "Potential credential material detected."
  exit 1
fi

echo "Final audit script completed. Runtime smoke/recovery evidence still belongs to the deployment environment."
