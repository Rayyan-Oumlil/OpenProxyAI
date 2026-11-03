#!/bin/sh
# Sends real requests through a running gateway and checks each outcome. POSIX sh + curl only.
# Used by the demo compose file (to fill the console with data) and by scripts/smoke.sh (as the checks).
#
#   BASE_URL   gateway, default http://localhost:8000
#   API_KEY    proxy key, default the seeded demo key
#   FAKE_URL   fake upstream; when set, also checks that the cached repeat never reached it
#
# Exits 1 if any outcome differs from what the demo policy should produce.
BASE_URL="${BASE_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-opai_dev_demo0001_00000000000000000000000000demo01fea5}"
CHAT="$BASE_URL/v1/chat/completions"
failures=0

# chat <label> <expected status> <user message>
chat() {
  label="$1"; want="$2"; message="$3"
  got=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$CHAT" \
    -H "Authorization: Bearer $API_KEY" -H 'Content-Type: application/json' \
    -d "{\"model\":\"openai/gpt-4o-mini\",\"messages\":[{\"role\":\"user\",\"content\":\"$message\"}]}")
  if [ "$got" = "$want" ]; then verdict="ok  "; else verdict="FAIL"; failures=$((failures + 1)); fi
  printf '%s %-34s expected %s got %s\n' "$verdict" "$label" "$want" "$got"
}

upstream_calls() {
  curl -s "$FAKE_URL/__calls" | grep -o '"model"' | wc -l | tr -d ' '
}

[ -n "$FAKE_URL" ] && before=$(upstream_calls)

chat "allowed request"            200 "Summarise our Q3 roadmap in one line."
chat "identical request (cached)" 200 "Summarise our Q3 roadmap in one line."
chat "policy: blocked keyword"    403 "What is the status of project-phoenix?"
chat "policy: PII (SSN)"          403 "Customer SSN is 123-45-6789, draft the email."
chat "another allowed request"    200 "Translate good morning to French."

if [ -n "$FAKE_URL" ]; then
  after=$(upstream_calls)
  reached=$((after - before))
  # Three allowed requests, but the repeat is served from cache: two reach the upstream, the two blocks none.
  if [ "$reached" = "2" ]; then verdict="ok  "; else verdict="FAIL"; failures=$((failures + 1)); fi
  printf '%s %-34s expected 2 upstream calls, saw %s\n' "$verdict" "cache + blocks stay off the upstream" "$reached"
fi

if [ "$failures" -ne 0 ]; then
  echo "$failures check(s) failed"
  exit 1
fi
echo "all checks passed"
