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
  (off by default; leave it off on multi-tenant). The endpoint is validated when saved, checked again before each call (a key that
  stops validating is skipped; if all are skipped the request fails with 503 rather than using another credential), and **enforced on
  every connection** (`provider_client.py`, added in the egress pass below).

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

- **S4a done** (core, not yet on the request path). `routing_service`: authorized set = registry entries that are enabled, have an
  active key, are cleared for the request's class (the lower of the model's and its key's class), serve the org's region
  (`global` = any), are within the org's `max_risk_rating` and pass the policy allowlist; each exclusion has a reason in a fixed order.
  `choose_route` returns the requested model if authorized, otherwise nothing (never a substitute); `cap:NAME` picks the cheapest, then
  lowest-risk, then alphabetical authorized model with that capability. Hypothesis property tests (300 examples each) cover the
  invariants, and I checked they fail when the code is deliberately broken. New policy fields: `routing_mode` (`off` default,
  `log_only`, `enforce`) and `max_risk_rating`. **S4b** wires this into chat (fallback closure, cache, streaming) and **S4c** into embeddings.

- **S4b done** (chat). `_decide_route` runs after classification when `routing_mode` is not `off`: `log_only` records the decision, headers
  and a `route` trace stage and changes nothing; `enforce` refuses with 446 `no_authorized_model` before rate limiting and any upstream
  call, serves the model only through its registry key (`only_key_id`, no other key, never an env key), drops an unauthorized experiment
  variant for the model the caller asked for, ignores an unauthorized `x-openproxy-fallback-model`, resolves `cap:NAME`, and skips the
  semantic cache above `OFF_REGISTRY_MAX_DATA_CLASS`. Turning on `enforce` needs a routable model (409 otherwise). Deviations: exact-match
  cache keys are not class-aware, on purpose: routing runs before the cache and the model is already in the key, so a hit is always a model
  authorized for this request now. Mutation-tested: removing the registry-key restriction fails 4 of the 13 e2e routing tests. **S4c**: embeddings.

- **S4c done** (embeddings). Same decision, 446 refusal, registry-key-only serving, headers and `route` stage as chat; embeddings have no
  fallback header, experiments or `cap:` routing. **S4 is complete.** Remaining MVP slices: S5 (preview and shadow) and S6 (console).

- **Hardening pass after S4** (audit of every place request content can leave the gateway). Found and closed two bypasses: the
  playground compare endpoint had its own copy of key selection and no routing, and the evaluation hook sent prompt and response
  to an external endpoint regardless of data class. Both now follow the same rules. Redundancy removed: `SEMANTIC_CACHE_MAX_DATA_CLASS`
  became the single `OFF_REGISTRY_MAX_DATA_CLASS` rule (`may_leave_registry`), three copies of the evaluation scheduling became
  `_schedule_eval`, four copies of the region lookup became `app/utils/region.py`, three copies of the routing decision became
  `route_decision`, and the playground's duplicated key-selection code is gone (it also ran database calls concurrently on one session).
  Checked and fine: Langfuse, ClickHouse, webhooks and spend reports carry metadata only, never request text.
  Verified on the real stack, not only in tests: `scripts/smoke_routing.py` (run by `scripts/smoke.sh`, so by CI) walks the registry, `log_only`,
  `enforce`, capability routing, streaming, embeddings, the audit trail and the playground against the Docker image, and restores the demo.
  A real-browser pass found three bugs no test had: two invisible icon buttons (one older, on the MCP page) and a trace that showed
  "Policy: Allowed" beside a routing refusal. The trace now has a "Routing" line, and the Playwright audit measures icon contrast.

- **Egress pass on S1/S2** (the gap I had documented as "needs egress control" is closed). I first measured it: LiteLLM followed a
  `307` from a configured endpoint and re-sent the request, prompt included, to a different server. Now calls to a custom endpoint use
  a guarded client: redirects are never followed, the host is resolved per request and every answer must be an allowed address, the
  connection goes to that validated address (no gap between check and connect), TLS is verified against the hostname (tested with a
  real local CA), and the operator switch is re-read each request. Mutation-checked (follow redirects, drop the hostname check,
  connect without pinning, don't pass the client): each breaks tests. Consequences: custom endpoints are for the `openai` provider
  only (the only one whose client LiteLLM lets us supply), the demo compose enables `ALLOW_INTERNAL_PROVIDER_ENDPOINTS`, and the one
  IP rule now lives in `app/utils/ssrf.py` (save-time validation used its own copy). S2: a registry entry's key link is now a
  composite foreign key `(org_id, provider_key_id)`, so the database itself refuses a link to another org's key.

- **Classification coverage pass (S3).** Classification only describes what the detector can see, and routing trusts it. Checked first: text
  extraction already covers tool-call arguments, JSON nested in strings and unicode escapes, and fails closed on oversized input.
  Measured the detector with realistic variations and found it missed an SSN written with spaces, dots or a zero-width character, and
  called any 13-19 digit number a card (no Luhn check), so order numbers were treated as confidential. Blocking, redaction and
  classification each had their own regexes; they now share `app/services/pii_detection.py` (normalize, Luhn, issuable SSNs, one
  tested behavior). Known and documented: `data_class_map` names only fire for entities the detector can report (`email`, `ssn`,
  `payment_card`, or Presidio's types); bare nine-digit numbers, spelled-out emails and phone numbers are deliberately not detected.

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
