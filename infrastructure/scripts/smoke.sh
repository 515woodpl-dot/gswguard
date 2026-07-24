#!/usr/bin/env sh
set -eu

api_url="${API_URL:-http://127.0.0.1:8000}"
dashboard_url="${DASHBOARD_URL:-http://127.0.0.1:3000}"

curl --fail --silent --show-error "$api_url/health/live" >/dev/null
curl --fail --silent --show-error "$dashboard_url/health" >/dev/null
echo "GSWGuard smoke checks passed."
