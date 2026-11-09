# The 3-minute walkthrough

A script for showing OpenProxyAI to someone: what to type, what to click, what they should see. Every
outcome below is also checked automatically by `scripts/demo_traffic.sh` (it runs when the demo starts and
in `scripts/smoke.sh`), so the demo cannot drift away from this page without CI failing.

Start the demo first: `docker compose -f docker-compose.demo.yml up --build`, then open
http://localhost:5173 and sign in as `admin@example.com` / `DemoPass123!`. See [the demo page](./demo.md).

```bash
KEY=opai_dev_demo0001_00000000000000000000000000demo01fea5
INTERN=opai_dev_demo0002_00000000000000000000000000demo02741f
chat() { curl -s -w '\n -> HTTP %{http_code}\n' localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $1" -H 'Content-Type: application/json' \
  -d "{\"model\":\"openai/gpt-4o-mini\",\"messages\":[{\"role\":\"user\",\"content\":\"$2\"}]}"; }
```

## 0:00 One key, any model

> "Your teams use one OpenProxyAI key. We sit between them and the providers."

```bash
chat $KEY "Summarise our Q3 roadmap in one line."          # -> HTTP 200
```

Open **Request logs**: the request is there with model, tokens, cost and latency.

## 0:40 PII and secrets never reach the provider

> "Policy runs before the request leaves your network."

```bash
chat $KEY "Customer SSN is 123-45-6789, draft the email."  # -> HTTP 446, policy block
chat $KEY "What is the status of project-phoenix?"         # -> HTTP 446, blocked keyword
```

In **Request logs** click the blocked row, then **Open full trace**. The waterfall stops after *Policy
checks*: the provider was never called. *What happened* shows the verdict, the reason and the rule that
fired. That row is the audit record.

## 1:20 A budget that actually stops spend

> "The intern's key is capped at one cent a day."

```bash
chat $INTERN "Summarise the board deck [big-usage]"        # -> HTTP 200 (a large, costly answer)
chat $INTERN "And one more question."                      # -> HTTP 429, daily user budget reached
```

The second call is refused before it reaches the provider. The body says `user_budget_daily_usd`.
Spend shows up on the **Dashboard** (cost, delta, burn-down) once the first request is logged.

> Note: the per-user daily budget answers **429**, while `ARCHITECTURE_RULES.md` lists 402 for "budget exceeded" (402 is
> only used by the streaming pre-flight check). It is pinned in `tests/e2e/test_demo_seed.py`; changing it is
> a client-visible decision.

## 2:00 Agents and tools: a rug-pull, caught

> "Agents call tools through the same gateway. A tool that changes after you approved it is a classic attack."

Open **Connect > MCP servers**, click `github`. Three tools: `search_issues` approved, `create_issue`
waiting for review, and `deploy` **drifted**. The diff shows the live description now carries an injected
`<IMPORTANT>` instruction; agents keep seeing the approved text. Now try to call it:

```bash
curl -s localhost:8000/v1/mcp -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"github__deploy","arguments":{}}}'
# -> error -32004: refused, the server was never contacted
```

Press **Approve** on `create_issue` to show the review flow.

## 2:40 Close

Back on the **Dashboard**: requests, cost with change against the previous period, success rate, policy
blocks and the month's budget burn-down. Then **Provider health** for the routing side.

## Optional, 3 more minutes: route by data class

> "Which model may see which data? Decide it once, see the answer before it matters."

The demo org starts with an empty model registry and routing off, so nothing above changes. To show routing:

1. **Provider keys > Add key**: provider `openai`, API base `http://fake-llm:9090/v1`, tick *Internal endpoint*, most sensitive data it may receive `Confidential`. (The demo stack allows internal endpoints; production leaves that off.)
2. **Model registry**: register `openai/gpt-4o-mini` cleared for `Internal` and `openai/gpt-4o` cleared for `Confidential`, both through that key.
3. **Policy > Data and routing**: set routing to *Preview (log only)* and save.
4. In **Preview a request**, enter model `openai/gpt-4o-mini` and a prompt containing `123-45-6789`. The answer: class *Confidential (detected: ssn)*, refused because the model is not cleared for it, with the reason. Nothing was sent, logged or counted. Try `openai/gpt-4o`: it would be served.
5. Switch routing to *Enforce*, save, and send the same request with curl: **HTTP 446**, and the row in **Request logs** shows the routing decision.

`scripts/smoke_routing.py` runs these same steps against the real stack (it needs the empty registry, and puts it back), so this section cannot drift.

> Honest notes for the presenter: provider health shows "Not checked" until health checks are enabled
> (`PROVIDER_HEALTH_CHECK_ENABLED`); the `github` server URL is a placeholder, so **Sync now** fails by
> design; the demo uses a fake LLM, so answers are echoes.
