# Design history: what was decided and why

Condensed from the build plans (Phases 0 to 5, Nov 2026). Each entry is a decision that is not obvious from the code, with the reason. For what exists today, see [features.md](../features.md); for the schema, [database-schema.md](./database-schema.md).

## Product decisions
- **Name stays OpenProxyAI.** No rename work.
- **Wedge:** compliance evidence and MCP governance first, classification-aware routing third.
- **Licence:** Apache-2.0 core, paid modules in a separate commercial directory.
- **Pricing ladder:** Community free, Team $299/mo, Business $1,500/mo, Enterprise from $25k/yr.
- **Scope source:** the EIAG spec, built in stages. The wider vision paper (voice-first, "Slack for AI", family/school packages) is parked.
- **Policy blocks return 446 everywhere;** 403 is only for real authorization failures.
- **Accessibility wording:** "automated WCAG 2.1 A/AA checks pass", never "WCAG compliant". See [accessibility.md](../guides/accessibility.md).

## Routing and data classes (Phase 2)
- **Classes:** `public < internal < confidential < secret`. The effective class is the max of the org default, the caller's `X-OpenProxyAI-Data-Class` header (which can only raise it) and the classifier's output. Text too large to scan counts as `confidential`; an unknown header value is a 400.
- **Authorized set:** registry entries that are enabled, have an active key, are cleared for the class (the lower of the model's and its key's class), serve the org's region, are within `max_risk_rating` and pass the allowlist. **Every fallback comes from this set.** An empty set is a 446 `no_authorized_model` with zero upstream calls.
- **Never a substitute:** `choose_route` returns the requested model if authorized, otherwise nothing. `cap:NAME` picks the cheapest, then lowest-risk, then alphabetical.
- **`log_only` is the shadow mode** (decide, record, never refuse). There is no separate shadow-rules feature.
- **The preview never disagrees with the real pipeline:** an e2e table asks the preview, then sends the real request.
- **Custom endpoints are guarded at connection time,** not only at save time. LiteLLM was measured following a `307` and re-sending the prompt to another server. Now redirects are never followed, the host is resolved per request, the connection goes to the validated address, and TLS is checked against the hostname. Consequence: custom endpoints are for the `openai` provider only.
- **Detection is shared** (`pii_detection.py`: normalize, Luhn, issuable SSNs). Blocking, redaction and classification used to have separate regexes that disagreed. Not detected on purpose: bare nine-digit numbers, spelled-out emails, phone numbers.
- **Exact-match cache keys are not class-aware, on purpose:** routing runs before the cache and the model is in the key, so a hit is always a model authorized for this request.
- **Registry links are composite foreign keys** `(org_id, provider_key_id)`, so the database itself refuses a link to another org's key.

## Eval loop (Phase 3)
- **Feedback:** idempotent per `(org, request, score_name)`; any `proxy:llm` key in the org may score any request of the org (keys rotate, feedback arrives late); an unknown or foreign request is a 404 with the same body; comments are PII-redacted.
- **Payload capture is opt-in** (`payload_capture_sample_rate`, 0 = off) with an operator ceiling on data class the org cannot raise. Redact first, then cut to size.
- **Datasets:** admin only and audited; PII is refused twice on import; items outlive the captured payload; capped at 10,000 per dataset.
- **Eval runs:** one `model_runner` for policy, routing, key choice and audit; a spending cap per run; an item that cannot be scored is an error with a reason, never a zero; regex evaluators run under the `regex` package with a timeout; the judge prompt treats everything as data.
- **Adaptive A/B:** Beta posteriors; traffic floor 5%; nothing is decided before `min_samples_per_variant` (default 30, hard floor 20). **Default `delta` is 0.01, not 0.05, because of a measurement:** with repeated looks, 0.05 names a false winner between equal variants in 38 to 43% of trials, 0.01 in about 13%. A winner is recorded, never deployed.
- **Promotion gate:** opt-in. A run vouches only for the exact content it tested (fingerprint). Override is admin-only, needs a reason of 10+ characters and is audited.

## Conversation workspace (Phase 4)
- **History is data too:** a confidential turn must not reach a model cleared only for internal data after the model changes mid-conversation.
- **The model is the one the caller names.** No variant swap, no fallback: the history is filtered for this model, so quietly answering with another would invalidate the filter.
- **Two layers:** the builder withholds history by clearance, then the whole package is classified and goes through the unchanged routing check.
- **An answer takes the class of everything the model saw.** An exchange is atomic, classed by the more sensitive half. An unknown stored class counts as the highest.
- **Admins see metadata, not messages.** Reading another user's turns is a 404 even for an admin.
- **The context record is append-only at the database level** and stores a SHA-256 of what was sent.
- **Opt-in per org** (`conversations_enabled`): the first feature that stores what users said by design.

## API surface (Phase 5)
- **One shared pipeline** (`request_gate.admit` and the modality adapters) instead of a copy per endpoint, so the order and the refusals cannot differ. Chat keeps its own orchestration around the same gate.
- **`/v1/responses`** always sends `store=false` and refuses provider-side state unless a policy flag allows it.
- **Audio is uninspected input,** classified `confidential` unless the class map says otherwise.
- **Files and batches** are gateway-run jobs: every line goes through the governed runner.
- **Analytics query is structured, not SQL text:** every choice is an allowlist lookup and every value is bound. Raw SQL can come later behind a vetted parser.
- **Secrets:** a Vault path is valid only inside the org's own folder; a failure to reach the secret store fails hard for that key, never falls back to another key.
- **WASM plugins:** wasmtime without WASI, memory and fuel limits; can only add restrictions; fails closed in `enforce`.
