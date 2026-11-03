# Run the seeded demo

One command starts a complete OpenProxyAI on your machine with demo data. It needs Docker and nothing
else: no LLM provider key, no cost. The "LLM" behind it is a fake OpenAI-compatible server.

```bash
docker compose -f docker-compose.demo.yml up --build
```

The first run builds two images (backend and console), so it takes longer than later runs. When the
`traffic` container prints `all checks passed`, the stack is ready.

| What | Where |
|---|---|
| Admin console | http://localhost:5173 |
| API | http://localhost:8000 |
| Console login | `admin@example.com` / `DemoPass123!` |
| Proxy API key | `opai_dev_demo0001_00000000000000000000000000demo01fea5` |

These credentials are public demo values. Never reuse them anywhere real.

## What is in it

- **Policy** on the demo org: requests mentioning `project-phoenix` and requests containing PII are
  blocked before they reach the upstream (HTTP 403).
- **Request logs and audit rows** from a one-shot traffic job: allowed, cached and blocked requests.
- **An MCP server `github`** in `enforce` mode with three pinned tools: `search_issues` (approved),
  `create_issue` (pending review) and `deploy` (drifted: its live description carries an injected
  instruction while agents keep seeing the approved text). Open **Connect > MCP servers**.
  The server URL is a placeholder, so calling its tools or pressing **Sync now** fails by design: the
  gateway refuses private and unresolvable addresses.

## Try it

```bash
KEY=opai_dev_demo0001_00000000000000000000000000demo01fea5
curl -s localhost:8000/v1/chat/completions -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"hello"}]}'

# blocked by policy:
curl -s -w '\n%{http_code}\n' localhost:8000/v1/chat/completions -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"about project-phoenix"}]}'
```

## Check it and reset it

```bash
scripts/smoke.sh                                  # boots a fresh stack, checks it over HTTP, removes it
docker compose -f docker-compose.demo.yml down -v # wipe the demo data
```

`scripts/smoke.sh` needs `curl`; set `KEEP=1` to leave the stack running afterwards.
