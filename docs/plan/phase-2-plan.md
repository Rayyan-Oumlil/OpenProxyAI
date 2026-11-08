# Phase 2 implementation plan: classification-aware routing (MVP, about 17 days)

Design: `design-specs.md` §B. Decisions: D2 (lead with evidence and MCP, routing third), D5 (build Anis's EIAG spec in
stages; stage 1 is the routing prerequisites), D6 (policy blocks are 446). Phase 1 is done.

**Gate status:** the five buyer calls are not done. S1 and S2 are safe under any buyer answer (they are the EIAG
prerequisites). **Pause after S2 and review the call notes before S3.**

## Rules for every slice
- One PR per slice, merged only with green CI. Test through the real pipeline against the fake upstream.
- New table: RLS policy, `app_user` grants and an isolation test (org A cannot see org B).
- Update `docs/features.md` only for what is true after the slice. New route: wire it in `main.py`.
- Never relax a route's admin check. Provider keys stay encrypted. Sidecar rules from `ARCHITECTURE_RULES.md` still apply.

## Slices

| # | Slice | Days | Done when |
|---|---|---|---|
| S1 | **Provider keys can point anywhere.** Migration adds `api_base`, `max_data_class` (default `internal`), `is_internal` to `llm_provider_keys`. `api_base` is passed to both `acompletion` calls (`llm_service.py` streaming near line 834 and non-streaming near 1109) and to health checks. Admin API and console key form get the fields. `api_base` is validated (https unless `is_internal`; reuse the webhook SSRF guard; refuse in AIRGAP_MODE only if external). | 3 | A fake upstream on another port receives the call via `api_base`; invalid or SSRF-prone URLs are rejected at save; existing keys behave exactly as before (regression test). |
| S2 | **Model registry.** `model_registry` table (design §B columns), RLS, CRUD `/api/v1/model-registry` (admin only), service with an org-scoped cache. Registry rows link to a `provider_key_id`. Nothing routes by it yet. | 3 | CRUD works; RLS isolation test; a registry row referencing another org's key is rejected. |
| | **Review call notes. Confirm or reshape S3 to S6.** | | |
| S3 | **Data classes and classification.** `public < internal < confidential < secret`. Effective class = max(key/team default, `x-openproxy-data-class` header which can only raise, classifier output). Presidio detections map to a class through a per-org `class_map`. Presidio moves off the event loop (thread pool) here. | 2 | Property test: the header can never lower the class; `US_SSN` in a prompt yields at least confidential; classification cost shows in the request trace. |
| S4 | **Router and fallback closure.** Authorized set = registry ∩ allowlist ∩ `max_data_class >= class` ∩ region ∩ risk. A concrete model must be in the set; `cap:NAME` matches by capability. Key selection, weights, adaptive LB and circuit breaker run inside the set only. **Every fallback comes from the same set:** fallback header, experiment variants, env keys, semantic-cache embeddings, streaming retries. Empty set: 446 `no_authorized_model`, zero upstream calls. Cache keys become class-aware. Headers `X-OpenProxyAI-Data-Class`, `-Route-Model`, `-Route-Reason` and a `routing_decision` in `request_metadata`. | 4 | Hypothesis property test (random registries, classes, regions, failing upstreams, random fallbacks): the fake upstream records every `(model, api_base, key_id)` and none violates the class or region; empty set means zero calls. |
| S5 | **Preview and shadow.** `POST /v1/policy/preview` runs classify and route with no upstream call and no log. Routing rules can be `shadow=true`: logged, never enforced. | 3 | Preview makes no upstream call and writes no `request_logs` row; shadow never changes the response. |
| S6 | **Console.** Model registry page (list, edit, enable), data class and `api_base` on the key form, routing decision shown in the request trace. Keyboard e2e and axe cover the new pages. | 2 | e2e and axe pass; the demo seed includes a small registry and one routed-by-class example in the walkthrough. |

## Slice status
- **S1 done.** Provider keys have `api_base`, `max_data_class`, `is_internal`. Chat, streaming, embeddings, playground compare and
  the health check honor `api_base`. Private or http endpoints need the operator setting `ALLOW_INTERNAL_PROVIDER_ENDPOINTS`
  (off by default; leave it off on multi-tenant). The endpoint is validated at save time and again on every use
  (30 s cache); a key that stops validating is skipped, and if all are skipped the request fails with 503 rather than
  falling back to the gateway's own key. Known limits, to close before offering this to untrusted tenants: the gap
  between that check and LiteLLM's own DNS lookup (DNS rebinding), and LiteLLM's HTTP client possibly following
  redirects from a validated host. The fix for both is egress control (network policy or an egress proxy), not more
  application checks.

- **S2 done.** `model_registry` table (RLS forced, audited), admin-only CRUD. Deviations from §B, on purpose: the endpoint comes
  from the linked provider key (no `api_base` or `internal` columns to drift apart), `regions` is required (no permissive
  default), and there is no org-scoped cache yet because nothing reads the registry before S4. A model's data class cannot exceed
  its key's at write time; S4 must still take the minimum, because a key's class can be lowered later.

- **S3 done.** `classification_service`: effective class = max(org default, caller header which can only raise, mapped PII
  entities); unknown header value is a 400; text too large to scan counts as `confidential`; recorded in the audit row
  metadata and the trace, returned as `X-OpenProxyAI-Data-Class`. Org defaults live in the policy config
  (`default_data_class`, `data_class_map`), no new table. Not done, deliberately: per-API-key and per-team default
  classes (needs buyer input on who sets them), and a console form for the two policy fields. Presidio scans now run in a
  worker thread, for classification and for the existing policy check.

## After the MVP (not in these 17 days)
Guardrail plugin runner with manifests, CEL rules (Rust binding behind an `ExprEngine` interface), bindings with
`locked`, external adapters (signed webhook, Bedrock, Azure Content Safety). Scope them from buyer feedback.

## Risks
- **Silent downgrade:** the failure that matters is a fallback quietly sending restricted data to a lower-trust
  model. S4's property test is the control; do not merge S4 without it.
- **Cache leak:** cached answers must never cross data classes (key includes the class).
- **Latency:** classification and routing run on every request. Measure with the stage timer; budget a few ms.
- **Scope creep:** CEL, plugins and adapters are tempting. They are out of the MVP on purpose.
- **Migration chain:** add one migration per slice on top of the current head; never edit applied migrations.
