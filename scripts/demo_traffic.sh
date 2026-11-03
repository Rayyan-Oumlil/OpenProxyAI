#!/bin/sh
# Sends real requests through a running gateway and checks each outcome. POSIX sh + curl only.
# Used by the demo compose file (to fill the console with data) and by scripts/smoke.sh (as the checks).
# It is also the demo walkthrough in executable form: see docs/getting-started/walkthrough.md.
#
#   BASE_URL    gateway, default http://localhost:8000
#   API_KEY     proxy key, default the seeded demo key
#   INTERN_KEY  budget-limited key, default the seeded intern key ($0.01 per day)
#   FAKE_URL    fake upstream; when set, also checks which requests reached it
#
# Exits 1 if any outcome differs from what the demo policy should produce.
BASE_URL="${BASE_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-opai_dev_demo0001_00000000000000000000000000demo01fea5}"
INTERN_KEY="${INTERN_KEY:-opai_dev_demo0002_00000000000000000000000000demo02741f}"
CHAT="$BASE_URL/v1/chat/completions"
failures=0

report() { # report <label> <expected> <got>
  if [ "$3" = "$2" ]; then verdict="ok  "; else verdict="FAIL"; failures=$((failures + 1)); fi
  printf '%s %-38s expected %s got %s\n' "$verdict" "$1" "$2" "$3"
}

status_of() { # status_of <key> <user message>
  curl -s -o /dev/null -w '%{http_code}' -X POST "$CHAT" \
    -H "Authorization: Bearer $1" -H 'Content-Type: application/json' \
    -d "{\"model\":\"openai/gpt-4o-mini\",\"messages\":[{\"role\":\"user\",\"content\":\"$2\"}]}"
}

chat() { # chat <label> <expected status> <user message>
  report "$1" "$2" "$(status_of "$API_KEY" "$3")"
}

upstream_calls() {
  curl -s "$FAKE_URL/__calls" | grep -o '"model"' | wc -l | tr -d ' '
}

[ -n "$FAKE_URL" ] && before=$(upstream_calls)

echo "-- governance: allow, cache, policy"
chat "allowed request"            200 "Summarise our Q3 roadmap in one line."
chat "identical request (cached)" 200 "Summarise our Q3 roadmap in one line."
chat "policy: blocked keyword"    403 "What is the status of project-phoenix?"
chat "policy: PII (SSN)"          403 "Customer SSN is 123-45-6789, draft the email."
chat "another allowed request"    200 "Translate good morning to French."

echo "-- cost control: the intern key has a \$0.01 daily budget"
report "intern: one expensive request" 200 "$(status_of "$INTERN_KEY" "Summarise the board deck [big-usage]")"
# Spend is recorded in the background, so the budget bites a moment later.
got=200
for _ in 1 2 3 4 5 6 7 8; do
  got=$(status_of "$INTERN_KEY" "And one more question.")
  [ "$got" != "200" ] && break
  sleep 1
done
report "intern: next request is stopped" 429 "$got"

echo "-- MCP: a tool whose definition changed after approval"
mcp=$(curl -s -X POST "$BASE_URL/v1/mcp" -H "Authorization: Bearer $API_KEY" -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"github__deploy","arguments":{}}}')
if echo "$mcp" | grep -q -- '-32004'; then mcp_result="-32004"; else mcp_result="allowed"; fi
report "drifted tool github__deploy is denied" "-32004" "$mcp_result"

if [ -n "$FAKE_URL" ]; then
  reached=$(($(upstream_calls) - before))
  # Reached the provider: the allowed prompt, the translation (the repeat came from cache) and the intern's
  # expensive request. Not reached: both policy blocks and the budget-stopped request.
  report "only permitted requests reach the provider" 3 "$reached"
fi

if [ "$failures" -ne 0 ]; then
  echo "$failures check(s) failed"
  exit 1
fi
echo "all checks passed"
