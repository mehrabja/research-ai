#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
API_PREFIX="${API_PREFIX:-/api/v1}"
API_KEY="${API_KEY:-}"

curl_args=(--fail --silent --show-error)
if [[ -n "$API_KEY" ]]; then
  curl_args+=(-H "X-API-Key: $API_KEY")
fi

curl "${curl_args[@]}" "$BASE_URL$API_PREFIX/health"
curl "${curl_args[@]}" "$BASE_URL$API_PREFIX/health/ready"
curl "${curl_args[@]}" "$BASE_URL$API_PREFIX/providers/matrix"

echo
echo "Production API smoke surface is reachable."
