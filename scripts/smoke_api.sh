#!/usr/bin/env bash
set -euo pipefail
BASE_URL="${BASE_URL:-http://localhost:8000}"
curl --fail --silent --show-error "$BASE_URL/api/v1/health"
curl --fail --silent --show-error "$BASE_URL/api/v1/health/ready"
echo
echo "API smoke checks passed."
