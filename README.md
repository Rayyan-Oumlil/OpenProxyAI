# OpenProxyAI

An LLM gateway for organizations that must prove what their AI did. It sits between your applications and model providers (OpenAI, Anthropic, Azure, Mistral and 100+ more through LiteLLM) and applies policy, data-class routing, budgets and an immutable audit trail to every request, including MCP tool calls.

It is OpenAI-compatible: change the `base_url`, keep your SDK.

## What it does

- **Policy:** PII and keyword blocking, prompt-injection detection, response guardrails, model allowlists, compliance templates (HIPAA, PCI-DSS, FedRAMP-aligned), sandboxed WebAssembly plugins. Policy blocks return HTTP 446 with a plain-language explanation.
- **Classification-aware routing:** each request gets a data class (`public` < `internal` < `confidential` < `secret`); a model registry decides which models and keys may serve it, with no silent fallback. A policy preview shows the decision without sending anything.
- **MCP gateway:** one endpoint for all your MCP tool servers, with tool pinning, injection scanning, per-caller grants, virtual bundles and taint tracking.
- **Cost and limits:** per-org, per-team, per-user and per-model rate limits and budgets, anomaly alerts, spend reports.
- **Endpoints:** chat (streaming), embeddings, rerank, images, audio, Responses, files and batches, realtime WebSocket.
- **Evaluation loop:** feedback, opt-in payload capture, datasets, evaluators, eval runs, adaptive A/B experiments, a prompt promotion gate.
- **Conversations:** threads that survive a model switch without leaking more-sensitive history to a less-cleared model.
- **Identity and audit:** RBAC, OIDC SSO, SCIM 2.0 (Okta, Entra ID), tenant isolation with Postgres row-level security, append-only logs, SIEM and OpenTelemetry export.
- **Operations:** Docker Compose, Helm chart, air-gap mode, Vault and AWS Secrets Manager for provider keys, Prometheus metrics.

The full inventory is in [docs/features.md](docs/features.md).

## Try it in one command

Needs Docker. No provider key and no cost: the "LLM" is a fake OpenAI-compatible server.

```bash
docker compose -f docker-compose.demo.yml up --build
```

Then open http://localhost:5173 and sign in as `admin@example.com` / `DemoPass123!` (public demo values; never reuse them). See [the demo page](docs/getting-started/demo.md) and the [3-minute walkthrough](docs/getting-started/walkthrough.md).

## Repository

| Path | What |
|---|---|
| `backend/` | FastAPI gateway and management API, Alembic migrations, tests |
| `admin-console/` | React admin console |
| `web-app/` | Marketing website |
| `docs-site/` | Public documentation site (Docusaurus) and blog |
| `docs/` | Operator and developer documentation, start at [docs/README.md](docs/README.md) |
| `sdk/` | Python and TypeScript SDKs |
| `deploy/` | Helm chart and cluster setup |
| `scripts/` | Demo smoke tests |

Architecture conventions live in [ARCHITECTURE_RULES.md](ARCHITECTURE_RULES.md).

## Develop

```bash
cd backend && pip install -r requirements.txt && pytest     # some suites need Postgres and Redis
cd admin-console && npm ci && npm run dev
```

CI runs backend tests, console lint, types, unit and Playwright suites (including axe accessibility checks), and the demo smoke test.

## Accessibility

Automated WCAG 2.1 A/AA checks pass on every console screen. See [docs/guides/accessibility.md](docs/guides/accessibility.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
