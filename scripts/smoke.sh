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
BASE_URL="$API" FAKE_URL="http://localhost:9090" "$PYTHON" scripts/smoke_routing.py; check "routing: registry, modes, refusals, audit, playground" $?

# Feedback endpoint on the real image and database: rate an answer with an API key, read the row back.
BASE_URL="$API" "$PYTHON" scripts/smoke_feedback.py; check "feedback: rate an answer, upsert, redaction, refusals" $?

# Opt-in payload capture on the real image and database: redaction, the data-class ceiling, expiry and the purge job.
BASE_URL="$API" "$PYTHON" scripts/smoke_capture.py; check "capture: opt-in, redaction, ceiling, streaming, expiry, purge" $?

# The eval loop's data path with the real login: capture, feedback, dataset, filtered import, PII refusal, delete.
BASE_URL="$API" "$PYTHON" scripts/smoke_datasets.py; check "datasets: capture -> feedback -> import with filters -> delete" $?

# Evaluators and eval runs with the real executor: exact, regex and judge runs, spending cap, cancel, active-run limit.
BASE_URL="$API" "$PYTHON" scripts/smoke_evals.py; check "evals: exact, regex, judge, spending cap, cancel, run limit" $?

# Adaptive A/B: real traffic is split, feedback is linked to its variant, and the real job names a winner.
BASE_URL="$API" "$PYTHON" scripts/smoke_adaptive.py; check "adaptive: split, linked feedback, no early move, winner and stop" $?

# Prompt promotion gate with a real eval run: draft, refusal without a run, promotion, override, stale run.
BASE_URL="$API" "$PYTHON" scripts/smoke_promotion.py; check "promotion gate: draft, refusal, run, promote, override, stale run" $?

# Conversations: one thread across two models, and the model cleared for less never receives the confidential turn.
BASE_URL="$API" FAKE_URL="http://localhost:9090" "$PYTHON" scripts/smoke_conversations.py; check "conversations: opt-in, held-back history, record of what was sent, refusals" $?

# The non-chat endpoints (images, audio, responses) through the shared pipeline: what the provider received, and policy/routing on each.
BASE_URL="$API" FAKE_URL="http://localhost:9090" "$PYTHON" scripts/smoke_modalities.py; check "modalities: images, speech, transcription, responses; policy and routing on each" $?

if [ "$failures" -ne 0 ]; then echo "$failures smoke check(s) failed"; exit 1; fi
echo "smoke passed"
