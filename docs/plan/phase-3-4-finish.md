# Finishing Phase 3 and building Phase 4

Status: started 2026-11-10. Phase 3's six backend slices are merged (see `phase-3-plan.md`). This plan covers what was left,
then Phase 4 (the conversation workspace, `design-specs.md` §D).

## Phase 3: what "finished" means
The eval loop works through the API but nobody can see or operate it without curl. Finished means:

| # | Item | Why |
|---|---|---|
| 3A (done, PR open) | Console pages: Datasets, Evaluators, Eval runs (a new "Evaluate" nav group) | The loop is invisible without them |
| 3B (done, PR open) | Experiments page: adaptive settings, per-variant chance of being best, winner. Policy page: capture rate and promotion gate settings. Prompt templates: draft status and a promotion panel | The other three slices have a UI-less control surface |
| 3C (done, PR #75) | The playground uses `services/model_runner.py` instead of its own copy of policy, routing, key choice and logging | Two copies of the same security-relevant sequence will drift |
| 3D (done, PR open) | Accessibility (axe, keyboard, reflow) for every new screen, in the existing e2e suites | The repo's standard for every console screen |

Cut, deliberately: `/v1/responses` and `/v1/rerank` (a pipeline refactor and a separate decision), and the read-only SQL view.

## Phase 4: conversation workspace
**Today** the gateway is stateless: the app sends the whole history on every call. **Phase 4** makes the gateway keep a
conversation and, before each call, decide which earlier turns the chosen model may see.

The reason it exists here, and not in a generic chat product: *history is data too.* A confidential turn 3 must not reach a
model cleared only for Internal data on turn 4. Phase 2 stops one request reaching the wrong model; Phase 4 stops history
leaking when the model changes mid-conversation.

### Design decisions (from the spec, with the calls I am making)
- **Model first, then context.** The turn endpoint settles the final model (including experiment variant and a refused fallback)
  *before* it builds the context, because the context depends on the model's clearance.
- **A turn's class is its own.** Each stored turn has a data class (the org default, raised by detected PII or the caller's
  assertion, like a request). The context for a model includes only turns at or below the model's clearance. The withheld
  turns are listed, with a reason, in an append-only `context_packages` row: *what was sent* is auditable.
- **Withholding is explicit to the user.** The reply says which earlier turns the model did not see. Silently dropping context
  would produce answers that make no sense and hide why.
- **The new message is never withheld.** If the model cannot see the message it is being asked to answer (its class is above the
  model's clearance), the turn is refused with the same 446 routing refusal a request would get, not answered blind.
- **No silent fallback.** A fallback model is used only if it is authorized for the *whole* context that would be sent; otherwise
  the package is rebuilt for it, and if the new message is above it, the turn fails. Never an unauthorized model.
- **Stored text is redacted** (same detector as payload capture) and capped, and a conversation's turns follow the org's
  retention. Conversations are opt-in per org (`conversations_enabled`), because this is the first feature that stores what
  users said by design.
- **Ownership and visibility:** a conversation belongs to one user and is `private` (default) or `team`. Row-level security keeps
  orgs apart; an application rule (owner, or teammate when `team`, or an admin for audit) keeps users apart inside an org.
  The user-level rule is enforced in the API *and* proven by a test per route, because RLS here is by org only.
- **Everything goes through `model_runner`**, so policy, routing, key selection, metering and the audit log apply to a
  conversation turn exactly as to any request (`source = conversation`).
- **Streaming** is out of the first cut (the spec defers it); the turn endpoint returns the whole reply.
- **Deferred, as in the spec:** memory tiers, RAG, personas, org-level sharing, a separate chat site, voice.

### Slices
| # | Slice | Status |
|---|---|---|
| 4.1 | Tables, RLS, org setting, conversation CRUD, ownership and visibility rules | done |
| 4.2 | The context builder (pure): which turns a model may see, token budget, exclusion reasons; property tests | done |
| 4.3 | `POST /conversations/{id}/turns`: classify, settle model, build package, call, store, audit | done |
| 4.4 | Console: conversation list and thread, per-turn model picker, "context sent" drawer showing what was withheld | done |
| 4.5 | Docs, smoke test on the real stack, accessibility, wrap-up | done |

## Working rules for this stretch
Same as Phase 3: spec first, tests first, a real-stack smoke script per slice, mutation checks on every rule that guards data,
dated docs, a PR per slice with CI green before merge.

## Progress notes
- **3A/3B/3D (console):** Datasets, Evaluators and Eval runs pages; Policy "Evaluation" tab; adaptive settings and results on Experiments; promotion dialog on draft prompts. 61 new component tests, 350 in all; axe, icon contrast, reflow and keyboard checks cover every new screen and dialog in both themes.
- **Found by those checks, fixed at the root:** (1) the `policy` badge failed AA contrast in the light theme (also on the logs drawer); (2) any dialog opened from a plain button lost focus on close, repo-wide, now fixed in `DialogContent`; (2b) **no dialog in the console was centred** (Tailwind's translate utilities need its base layer, which the app does not load), so a tall dialog ran off the bottom of the window with its buttons out of reach, now centred with a plain transform and pinned by an e2e test that fails on the old code; (3) the Experiments "View results" toggle's visible text did not match its accessible name; (4) a keyboard e2e test that pressed two keys without waiting was unstable on the unchanged base (5 of 6 runs failed), now deterministic.
- **A trap avoided:** the Experiments edit form always sent `variants`, which makes the server replace them and detach every rating, so editing the name of an adaptive test would have wiped its data. It now sends them only when they changed.
- **Found only by driving the real console against the real backend** (not by the mocked tests): the oversized textarea (a global 190px min-height), the invisible "Edit" button on Experiments (green text on a green button), the results panel squeezed into the Actions column and clipped, the dialog off-screen, and a race where saving one dataset item wiped the next one the user had started typing. Each has a regression test; the dialog and textarea ones were confirmed to fail on the old code.

### Phase 4: what was decided while building (2026-11-11)
- **The model is the one the caller names.** The first design had the turn endpoint swap in experiment variants and fall back to another model. Dropped: the history is filtered for *this* model, so quietly answering with another invalidates the filter, and a swap mid-conversation is surprising. A failed call returns an error and stores nothing.
- **Two layers, not one.** The builder withholds history by clearance; then the whole package (system prompt, kept history, new message) is classified as the highest of its parts and goes through the unchanged routing check. A test replaces the builder with one that ignores clearance and shows routing still refuses.
- **An answer takes the class of everything the model saw** (it may quote any of it). Consequence: once a confidential turn is in a model's context, later answers are confidential and stay withheld from less-cleared models. Conservative on purpose.
- **An exchange (question + answer) is atomic**, classed by the more sensitive of the two. An unknown stored class counts as the highest.
- **Admins see metadata, not messages.** `scope=org` lists titles, owners and sizes; reading another user's turns is a 404 even for an admin. An admin may delete (audited without content).
- **The context record is append-only at the database level** (REVOKE UPDATE/DELETE; found because default privileges had silently granted them, and a test caught it). It stores a SHA-256 of the exact messages sent instead of a second copy of the text.
- `team` visibility with a deleted team degrades to private (a CHECK demanding a team would have made deleting a team fail; found by a test).
- Not done, on purpose: streaming, memory tiers, RAG, personas, org-wide sharing, a log_only preview of what *would* be withheld (log_only and off send the whole history; the record says which mode applied).

### Found by the commit security review and the real-console walk
- The **system prompt** was sent to the model without being classified, so a sensitive one could reach an under-cleared model. Now part of the package class. Test fails without the fix.
- The **rate limit** was counted on the new message only. Now on the whole package. Test fails without the fix.
- The message **Sensitivity** choice stuck after the first send, so the next, unrelated message was silently treated as confidential and refused. Now resets after each send.
- A drawer opened by a plain button did not return focus to it on close (the same bug fixed earlier for dialogs). Fixed in `SheetContent`, with a test that fails on the old code.
- The label "This message is" collided with "Message" for assistive technology; renamed "Sensitivity". The model field showed a free-text box while the list loaded; now a disabled "Loading models…" select.
