#!/bin/sh
# End-to-end smoke test on real services: boots the demo stack (Postgres, Redis, fake upstream, API,
# console), checks it over HTTP with curl, then removes it. Needs Docker and curl.
#
#   scripts/smoke.sh            boot, check, tear down (volumes included)
#   KEEP=1 scripts/smoke.sh     leave the stack running afterwards
set -eu
cd "$(dirname "$0")/.."

COMPOSE="docker compose -f docker-compose.demo.yml"
API="http://localhost:8000"
ADMIN_EMAIL="admin@example.com"
ADMIN_PASSWORD="DemoPass123!"
failures=0

check() { # check <label> <ok: 0|1>
  if [ "$2" = "0" ]; then echo "ok   $1"; else echo "FAIL $1"; failures=$((failures + 1)); fi
}

cleanup() {
  if [ "${KEEP:-0}" = "1" ]; then echo "KEEP=1: stack left running (down with: $COMPOSE down -v)"; else $COMPOSE down -v >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT

# Start from nothing so the seed and migrations are exercised, not a leftover state.
$COMPOSE down -v >/dev/null 2>&1 || true
$COMPOSE up -d --build --wait api console

[ "$(curl -s -o /dev/null -w '%{http_code}' "$API/health")" = "200" ]; check "API health" $?
[ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:5173/)" = "200" ]; check "console serves the SPA" $?
[ "$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/v1/chat/completions" -H 'Content-Type: application/json' -d '{}')" = "401" ]; check "no key is rejected (401)" $?

token=$(curl -s -X POST "$API/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
[ -n "$token" ]; check "seeded admin can log in" $?
curl -s "$API/api/v1/mcp-servers" -H "Authorization: Bearer $token" | grep -q '"name":"github"'; check "seeded MCP server is listed" $?

BASE_URL="$API" FAKE_URL="http://localhost:9090" sh scripts/demo_traffic.sh; check "pipeline: allow, cache, policy blocks" $?

# Classification-aware routing on the real image: registry, log_only, enforce, capability routing, playground.
PYTHON=$(command -v python3 || command -v python)
BASE_URL="$API" "$PYTHON" scripts/smoke_routing.py; check "routing: registry, modes, refusals, audit, playground" $?

if [ "$failures" -ne 0 ]; then echo "$failures smoke check(s) failed"; exit 1; fi
echo "smoke passed"
